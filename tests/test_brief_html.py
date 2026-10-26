"""Render del brief a HTML: bloques cercados para copiar."""
import unittest
from secretary.brief_html import render


class BriefHtmlTests(unittest.TestCase):
    def test_bloque_cercado_sale_como_pre_sin_fences(self):
        md = '## ✅ Requiere tu decisión\n\n1. Decide X\n\n```text\n1: sí\n2: <posponer>\n```\n'
        out = render(md, 'Brief', 'https://example.test/1', '2026-10-26')
        self.assertIn('<pre', out)
        self.assertIn('1: sí\n2: &lt;posponer&gt;', out)
        self.assertNotIn('```', out)


if __name__ == '__main__':
    unittest.main()
