from unittest import mock

from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from inv import gate

GATED = override_settings(MIDDLEWARE=[*settings.MIDDLEWARE, 'inv.gate.GatePasswordMiddleware'])


@GATED
class GateTests(TestCase):
    """The live site's password screen (inv/gate.py, switched on by inv/prod_settings.py)."""

    def test_every_page_asks_for_the_password_first(self):
        response = self.client.get('/')
        self.assertContains(response, 'name="gate_password"')

    def test_the_right_password_lets_you_in_for_the_session(self):
        with mock.patch.object(gate, 'GATE_PASSWORD', '4321'):
            response = self.client.post('/', {'gate_password': '4321', 'next': '/'})
        self.assertRedirects(response, '/', fetch_redirect_response=False)
        self.assertTrue(self.client.session['inv_gate_ok'])
        self.assertNotContains(self.client.get('/'), 'name="gate_password"')

    def test_a_wrong_password_is_refused(self):
        with mock.patch.object(gate, 'GATE_PASSWORD', '4321'):
            response = self.client.post('/', {'gate_password': '0000'})
        self.assertContains(response, '비밀번호가 틀렸습니다')
        self.assertNotIn('inv_gate_ok', self.client.session)

    def test_without_a_configured_password_nothing_opens_the_gate(self):
        # No fallback: a missing GATE_PASSWORD keeps the site shut rather than open to a known code.
        with mock.patch.object(gate, 'GATE_PASSWORD', ''):
            for typed in ('', '0000'):
                response = self.client.post('/', {'gate_password': typed})
                self.assertContains(response, '비밀번호가 틀렸습니다')
        self.assertNotIn('inv_gate_ok', self.client.session)

    def test_admin_static_and_app_files_skip_the_gate(self):
        passed = HttpResponse('the page itself')
        middleware = gate.GatePasswordMiddleware(lambda request: passed)
        factory = RequestFactory()
        for path in ('/admin/login/', '/static/app.css', '/manifest.json', '/sw.js', '/favicon.ico'):
            with self.subTest(path=path):
                request = factory.get(path)
                request.session = {}
                self.assertIs(middleware(request), passed)
        request = factory.get('/invoices/')
        request.session = {}
        self.assertIn(b'name="gate_password"', middleware(request).content)


class ProdSettingsTests(TestCase):
    def test_prod_settings_add_the_gate_last(self):
        from inv import prod_settings
        self.assertEqual(prod_settings.MIDDLEWARE[-1], 'inv.gate.GatePasswordMiddleware')
        self.assertEqual(prod_settings.MIDDLEWARE[:-1], settings.MIDDLEWARE)
