"""Scripts sin LLM de wiki-update: W0, inventario de pendientes y cierre (secretary/routines/ops/wiki-*)."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

OPS = Path(__file__).resolve().parents[1] / 'secretary/routines/ops'

# gh falso: responde desde un JSON de estado y registra cada llamada en $GH_LOG.
FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
state = json.load(open(os.environ["GH_STATE"]))
with open(os.environ["GH_LOG"], "a") as log:
    log.write(json.dumps(args) + "\n")
def arg(prefix):
    return next(a.split("=", 1)[1] for a in args if a.startswith(prefix))
if args[:2] == ["repo", "view"]:
    print(json.dumps({"owner": {"login": "owner"}, "name": "repo"}))
elif args[:2] == ["pr", "list"]:
    print(json.dumps(state["prs"]))
elif args[:2] == ["api", "graphql"]:
    n = arg("n=")
    print(json.dumps({"data": {"repository": {"pullRequest": state["details"][n]}}}))
elif args[:2] == ["pr", "merge"]:
    sys.exit(1 if int(args[2]) in state.get("fail_merge", []) else 0)
elif args[:3] == ["api", "-X", "PUT"]:
    n = int(args[3].split("/")[-2])
    sys.exit(1 if n in state.get("fail_api", []) else 0)
elif args[:2] == ["pr", "diff"]:
    print(state.get("diff", {}).get(args[2], ""))
'''

FAKE_SIG = """#!/usr/bin/env bash
[ "$2" = --mark ] && echo "<!-- mark:$1 -->" || echo "footer:$1"
"""

COMMIT_DATE = '2026-10-20T10:00:00Z'


def detail(*, mergeable: str = 'MERGEABLE', threads: list | None = None, comments: list | None = None,
           reviews: list | None = None) -> dict:
    return {'mergeable': mergeable, 'commits': {'nodes': [{'commit': {'committedDate': COMMIT_DATE}}]},
            'reviewThreads': {'nodes': threads or []}, 'comments': {'nodes': comments or []},
            'reviews': {'nodes': reviews or []}}


def note(body: str, when: str = '2026-10-21T10:00:00Z', login: str = 'owner', typename: str = 'User') -> dict:
    return {'body': body, 'createdAt': when, 'url': 'u', 'author': {'login': login, '__typename': typename}}


def pr(number: int, branch: str) -> dict:
    return {'number': number, 'headRefName': branch, 'title': f'chore: {number}'}


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        bin_dir = self.root / 'bin'; bin_dir.mkdir()
        (bin_dir / 'gh').write_text(FAKE_GH); (bin_dir / 'gh').chmod(0o755)
        sig = self.root / 'sig.sh'; sig.write_text(FAKE_SIG); sig.chmod(0o755)
        self.state = self.root / 'state.json'
        self.gh_log = self.root / 'gh.log'
        self.env = {**os.environ, 'PATH': f'{bin_dir}:{os.environ["PATH"]}', 'GH_STATE': str(self.state),
                    'GH_LOG': str(self.gh_log), 'SECRETARY_SIGNATURE': str(sig),
                    'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@localhost',
                    'GIT_COMMITTER_NAME': 't', 'GIT_COMMITTER_EMAIL': 't@localhost'}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def calls(self) -> list[list[str]]:
        if not self.gh_log.exists():
            return []
        return [json.loads(line) for line in self.gh_log.read_text().splitlines()]


class WikiW0Test(Base):
    def w0(self, prs: list, details: dict, *extra: str, **state: object) -> dict:
        self.state.write_text(json.dumps({'prs': prs, 'details': {str(k): v for k, v in details.items()}, **state}))
        out = subprocess.run([sys.executable, str(OPS / 'wiki-w0.py'), '--repo', str(self.root), *extra],
                             env=self.env, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def numbers(self, result: dict, key: str) -> list[int]:
        return [e['number'] for e in result[key]]

    def test_merges_clean_auto_prs_and_ignores_manual_branches(self) -> None:
        result = self.w0([pr(1, 'correo/auto-20261022-1811'), pr(2, 'fix/manual'),
                          pr(3, 'reuniones/auto-2026-10-22')], {1: detail()})
        self.assertEqual(self.numbers(result, 'merged'), [1])
        self.assertEqual(result['candidates'], 1)
        self.assertIn(['pr', 'merge', '1', '--merge'], self.calls())

    def test_dry_run_does_not_merge_or_close(self) -> None:
        result = self.w0([pr(1, 'drive/auto-20261021-0400'), pr(2, 'drive/auto-20261022-0400')],
                         {1: detail(), 2: detail()}, '--dry-run')
        self.assertTrue(result['dry_run'])
        self.assertEqual(self.numbers(result, 'merged'), [2])
        self.assertEqual(self.numbers(result, 'closed_superseded'), [1])
        self.assertFalse([c for c in self.calls() if c[:2] in (['pr', 'merge'], ['pr', 'close'])])

    def test_unresolved_inline_thread_goes_to_llm(self) -> None:
        thread = {'isResolved': False, 'comments': {'nodes': [{**note('renombra esto'), 'path': 'a.md', 'line': 3}]}}
        resolved = {'isResolved': True, 'comments': {'nodes': [note('ok')]}}
        result = self.w0([pr(1, 'wiki/auto-20261022-2348')], {1: detail(threads=[thread, resolved])})
        self.assertEqual(result['needs_llm'][0]['reason'], 'comentarios')
        self.assertEqual([c['body'] for c in result['needs_llm'][0]['comments']], ['renombra esto'])
        self.assertFalse(result['merged'])

    def test_general_comments_filter_agents_and_old_ones(self) -> None:
        agent = [note('<!-- agent-generated:x runtime=sesion -->\nhecho'), note('> 🤖 **wiki-update**\n\nlisto'),
                 note('texto\n\n---\n🤖 _Generado por Claude Code — x_'), note('bot', typename='Bot'),
                 note('pedido viejo', when='2026-10-19T10:00:00Z')]
        result = self.w0([pr(1, 'housekeeping/auto-20261023-0610'), pr(2, 'housekeeping/auto-20261023-0700')],
                         {1: detail(comments=agent), 2: detail(comments=[note('corrige el dato')])})
        self.assertEqual(self.numbers(result, 'merged'), [1])
        self.assertEqual(self.numbers(result, 'needs_llm'), [2])
        self.assertEqual(result['needs_llm'][0]['comments'][0]['kind'], 'general')

    def test_chained_closes_older_with_signed_comment(self) -> None:
        result = self.w0([pr(5, 'job-search/auto-20261022-0710'), pr(6, 'job-search/auto-20261023-0710')],
                         {5: detail(), 6: detail()})
        self.assertEqual(result['closed_superseded'], [{'number': 5, 'branch': 'job-search/auto-20261022-0710', 'title': 'chore: 5', 'superseded_by': 6}])
        close = next(c for c in self.calls() if c[:2] == ['pr', 'close'])
        self.assertEqual(close[2], '5')
        self.assertIn('Superado por #6', close[4])
        self.assertIn('<!-- mark:wiki-update -->', close[4])
        self.assertEqual(self.numbers(result, 'merged'), [6])

    def test_chained_older_with_comments_is_not_closed(self) -> None:
        result = self.w0([pr(5, 'drive/auto-20261022-0400'), pr(6, 'drive/auto-20261023-0400')],
                         {5: detail(comments=[note('no cierres esto')]), 6: detail()})
        self.assertEqual(result['needs_llm'][0]['reason'], 'superado-con-comentarios')
        self.assertFalse(result['closed_superseded'])

    def test_conflict_goes_to_llm(self) -> None:
        result = self.w0([pr(1, 'reuniones/auto-20261022-1241')], {1: detail(mergeable='CONFLICTING')})
        self.assertEqual(result['needs_llm'][0]['reason'], 'conflicto')
        self.assertFalse([c for c in self.calls() if c[:2] == ['pr', 'merge']])

    def test_merge_falls_back_to_api_then_reports_failure(self) -> None:
        result = self.w0([pr(1, 'correo/auto-20261022-1811'), pr(2, 'whatsapp/auto-20261022-1900')],
                         {1: detail(), 2: detail()}, fail_merge=[1, 2], fail_api=[2])
        self.assertEqual(self.numbers(result, 'merged'), [1])
        self.assertEqual(self.numbers(result, 'failed'), [2])
        self.assertTrue(any(c[:4] == ['api', '-X', 'PUT', 'repos/owner/repo/pulls/1/merge'] for c in self.calls()))

    def test_provenance_tsv(self) -> None:
        diff = ('+++ b/extractors/meetings/memory/acciones.md\n+## acc-20261022-001\n+- x: y\n'
                '+++ b/knowledge/wiki/articulos/a.md\n+## No cuenta\n')
        prov = self.root / 'prov.tsv'
        result = self.w0([pr(7, 'reuniones/auto-20261022-1241')], {7: detail()}, '--prov-out', str(prov),
                         diff={'7': diff})
        self.assertEqual(result['prov_rows'], 1)
        self.assertEqual(prov.read_text(), 'extractors/meetings/memory/acciones.md\t## acc-20261022-001\tPR#7\n')


MEMORY = """# Acciones

```markdown
## acc-YYYYMMDD-NNN
- pendiente_wiki: true
```

Cada item con `pendiente_wiki: true` se integra.

## acc-20261022-001
- tipo: compromiso
- estado: abierta
- email: no-se-copia
- pendiente_wiki: true

## acc-20261022-002
- pendiente_wiki: false  # integrado

## acc-20261022-003
- pendiente_wiki: true  # nota del extractor
"""

MEMO = """# Memo

### 1. Org nueva
- fuente: drive
- pendiente_wiki: true — org nueva, sin artículo.
"""


class WikiPendingTest(Base):
    def setUp(self) -> None:
        super().setUp()
        self.wt = self.root / 'wt'
        (self.wt / 'extractors/meetings/memory').mkdir(parents=True)
        (self.wt / 'extractors/drive/memory').mkdir(parents=True)
        (self.wt / 'extractors/meetings/memory/acciones.md').write_text(MEMORY)
        (self.wt / 'extractors/drive/memory/2026-10-22.md').write_text(MEMO)
        subprocess.run(['git', 'init', '-q', str(self.wt)], check=True)
        subprocess.run(['git', '-C', str(self.wt), 'add', '-A'], check=True)
        subprocess.run(['git', '-C', str(self.wt), 'commit', '-q', '-m', 'carga inicial'], check=True, env=self.env)

    def pending(self, *extra: str) -> dict:
        out = subprocess.run([sys.executable, str(OPS / 'wiki-pending.py'), '--wt', str(self.wt), *extra],
                             env=self.env, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_inventory_skips_fences_prose_and_false(self) -> None:
        result = self.pending()
        self.assertEqual(result['total'], 3)
        headers = [i['header'] for i in result['items']]
        self.assertEqual(headers, ['### 1. Org nueva', '## acc-20261022-001', '## acc-20261022-003'])
        acc = result['items'][1]
        self.assertEqual(acc['tipo'], 'accion')
        self.assertEqual(acc['campos'], {'tipo': 'compromiso', 'estado': 'abierta'})
        self.assertEqual(acc['linea'], 10)
        self.assertEqual(result['items'][2]['nota'], 'nota del extractor')
        self.assertEqual(result['items'][0]['tipo'], 'memo')
        self.assertEqual(result['items'][0]['nota'], 'org nueva, sin artículo.')

    def test_provenance_from_tsv_and_origin_commit(self) -> None:
        prov = self.root / 'prov.tsv'
        prov.write_text('extractors/meetings/memory/acciones.md\t## acc-20261022-001\tPR#9\n')
        result = self.pending('--prov', str(prov))
        by_header = {i['header']: i for i in result['items']}
        self.assertEqual(by_header['## acc-20261022-001']['procedencia'], 'PR#9')
        self.assertEqual(by_header['## acc-20261022-003']['procedencia'], 'preexistente')
        self.assertTrue(by_header['## acc-20261022-003']['commit_origen'].endswith('carga inicial'))
        self.assertEqual(result['por_procedencia'], {'pr': 1, 'preexistente': 2})

    def test_out_file_and_dry_run(self) -> None:
        out = self.root / 'pending.json'
        subprocess.run([sys.executable, str(OPS / 'wiki-pending.py'), '--wt', str(self.wt), '--out', str(out),
                        '--dry-run', '--no-origin'], env=self.env, check=True, capture_output=True)
        self.assertFalse(out.exists())
        subprocess.run([sys.executable, str(OPS / 'wiki-pending.py'), '--wt', str(self.wt), '--out', str(out),
                        '--no-origin'], env=self.env, check=True, capture_output=True)
        self.assertEqual(json.loads(out.read_text())['total'], 3)


FAKE_BUILD = """import os, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
(root / 'output').mkdir(exist_ok=True)
(root / 'output' / 'built').write_text(os.environ['SECRETARY_DATA'])
print(f"Generados {os.environ.get('FAKE_ARTICLES', '5')} artículos en {root / 'output'}")
"""

FAKE_DEPLOY = """#!/usr/bin/env bash
echo "$1" >> "$DEPLOY_LOG"; echo "publicado: abc"
"""


class WikiCloseTest(Base):
    def setUp(self) -> None:
        super().setUp()
        self.core = self.root / 'core'
        (self.core / 'wiki/build').mkdir(parents=True)
        (self.core / 'wiki/build/build.py').write_text(FAKE_BUILD)
        deploy = self.core / 'wiki/deploy-output.sh'; deploy.write_text(FAKE_DEPLOY); deploy.chmod(0o755)
        remote = self.root / 'remote.git'
        subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', str(remote)], check=True)
        self.repo = self.root / 'repo'
        subprocess.run(['git', 'clone', '-q', str(remote), str(self.repo)], check=True, capture_output=True)
        (self.repo / 'a.md').write_text('a\n')
        for cmd in (['add', '-A'], ['commit', '-q', '-m', 'init'], ['push', '-q', 'origin', 'main']):
            subprocess.run(['git', '-C', str(self.repo), *cmd], check=True, env=self.env)
        self.wt = self.root / 'wt-wiki'
        self.branch = 'wiki/auto-20261023-2300'
        subprocess.run(['git', '-C', str(self.repo), 'worktree', 'add', '-q', '-b', self.branch, str(self.wt),
                        'origin/main'], check=True)
        (self.wt / 'b.md').write_text('b\n')
        self.body = self.root / 'body.md'; self.body.write_text('Reporte.\n')
        self.deploy_log = self.root / 'deploy.log'
        self.state.write_text(json.dumps({'prs': [], 'details': {}}))
        self.env.update({'SECRETARY_CORE': str(self.core), 'SECRETARY_INSTANCE': str(self.repo),
                         'DEPLOY_LOG': str(self.deploy_log)})
        # gh falso de pr create: el genérico no imprime URL.
        (self.root / 'bin/gh').write_text(FAKE_GH + '\nif args[:2] == ["pr", "create"]:\n'
                                          '    body = args[args.index("--body-file") + 1]\n'
                                          '    open(os.environ["GH_LOG"] + ".body", "w").write(open(body).read())\n'
                                          '    print("https://github.com/owner/repo/pull/42")\n')

    def close(self, *extra: str, articles: str = '5') -> subprocess.CompletedProcess:
        return subprocess.run(['bash', str(OPS / 'wiki-close.sh'), '--wt', str(self.wt), '--branch', self.branch,
                               '--body-file', str(self.body), *extra], env={**self.env, 'FAKE_ARTICLES': articles},
                              capture_output=True, text=True)

    def result(self, out: subprocess.CompletedProcess) -> dict[str, str]:
        pairs: dict[str, str] = {}
        for line in out.stdout.strip().splitlines():
            pairs.update(part.split('=', 1) for part in shlex.split(line))
        return pairs

    def test_builds_deploys_and_opens_pr(self) -> None:
        out = self.close()
        self.assertEqual(out.returncode, 0, out.stderr)
        result = self.result(out)
        self.assertEqual((result['BUILD_ARTICLES'], result['DEPLOY'], result['RESULT']), ('5', 'published', 'pr'))
        self.assertEqual((self.core / 'wiki/output/built').read_text(), str(self.wt))
        self.assertTrue(self.deploy_log.read_text().startswith('sync-wiki '))
        create = next(c for c in self.calls() if c[:2] == ['pr', 'create'])
        self.assertIn('hilo:wiki', create)
        body = Path(str(self.gh_log) + '.body').read_text()
        self.assertIn('<!-- mark:wiki-update -->', body)
        self.assertIn('**Build y deploy:** 5 artículos generados; deploy: published.', body)

    def test_zero_articles_stops_before_deploy_and_pr(self) -> None:
        out = self.close(articles='0')
        self.assertEqual(out.returncode, 4)
        self.assertFalse(self.deploy_log.exists())
        self.assertFalse([c for c in self.calls() if c[:2] == ['pr', 'create']])

    def test_dry_run_has_no_side_effects(self) -> None:
        out = self.close('--dry-run')
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.result(out)['DEPLOY'], 'dry-run')
        self.assertFalse((self.core / 'wiki/output').exists())
        self.assertFalse(self.deploy_log.exists())
        self.assertFalse([c for c in self.calls() if c[:2] == ['pr', 'create']])
        self.assertTrue(self.wt.exists())


if __name__ == '__main__':
    unittest.main()
