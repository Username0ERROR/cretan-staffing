import os
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse


class SignupTests(TestCase):
    def setUp(self):
        self.owner_env = patch.dict(os.environ, {'STAFF_LOGIN_USERNAME': ''})
        self.owner_env.start()
        self.addCleanup(self.owner_env.stop)

    def test_candidate_can_sign_up_and_reaches_dashboard(self):
        response = self.client.post(reverse('signup'), {
            'username': 'newcandidate', 'email': 'candidate@example.com',
            'role': 'candidate', 'password1': 'a-long-password-123',
            'password2': 'a-long-password-123',
        })
        self.assertRedirects(response, reverse('dashboard'))
        user = User.objects.get(username='newcandidate')
        self.assertTrue(user.is_active)
        self.assertTrue(user.groups.filter(name='candidate').exists())

    def test_client_signup_requires_approval(self):
        response = self.client.post(reverse('signup'), {
            'username': 'newclient', 'email': 'client@example.com',
            'role': 'client', 'password1': 'a-long-password-123',
            'password2': 'a-long-password-123',
        })
        self.assertRedirects(response, reverse('login'))
        self.assertFalse(User.objects.get(username='newclient').is_active)

    def test_public_signup_cannot_create_admin(self):
        response = self.client.post(reverse('signup'), {
            'username': 'badrole', 'email': 'bad@example.com',
            'role': 'admin', 'password1': 'a-long-password-123',
            'password2': 'a-long-password-123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='badrole').exists())

    def test_service_accounts_have_no_interactive_password(self):
        from django.core.management import call_command
        call_command('provision_service_accounts')
        account = User.objects.get(username='svc_email')
        self.assertFalse(account.has_usable_password())
        self.assertFalse(account.is_active)
        self.assertTrue(account.groups.filter(name='service_account').exists())


class MaintenanceModeTests(TestCase):
    def setUp(self):
        self.owner_env = patch.dict(os.environ, {'STAFF_LOGIN_USERNAME': ''})
        self.owner_env.start()
        self.addCleanup(self.owner_env.stop)
        from .models import PlatformControl
        self.control = PlatformControl.get_solo()

    def test_manual_maintenance_blocks_public_pages_with_503(self):
        self.control.maintenance_mode = True
        self.control.save()
        response = self.client.get('/')
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, 'Platform temporarily locked.', status_code=503)

    def test_manual_maintenance_blocks_admin_but_allows_recovery(self):
        self.control.maintenance_mode = True
        self.control.save()
        self.assertEqual(self.client.get('/admin/').status_code, 503)
        self.assertEqual(self.client.get('/owner-recovery/').status_code, 200)

    def test_api_receives_json_503_during_maintenance(self):
        self.control.maintenance_mode = True
        self.control.save()
        response = self.client.get('/api/example/', HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error'], 'maintenance_mode')

    def test_site_is_available_by_default(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    @override_settings()
    def test_paused_owner_activates_deadlock_and_password_recovers(self):
        from .models import PlatformControl
        owner = User.objects.create_superuser(
            username='platformowner', email='owner@example.com', password='owner-test-password-123'
        )
        owner.is_active = False
        owner.save(update_fields=['is_active'])
        with patch.dict(os.environ, {'STAFF_LOGIN_USERNAME': 'platformowner'}):
            response = self.client.get('/')
            self.assertEqual(response.status_code, 503)
            self.assertIn('security lock', response.content.decode().lower())

            bad = self.client.post('/owner-recovery/', {'password': 'wrong-password'})
            self.assertEqual(bad.status_code, 200)
            owner.refresh_from_db()
            self.assertFalse(owner.is_active)

            good = self.client.post('/owner-recovery/', {'password': 'owner-test-password-123'})
            self.assertEqual(good.status_code, 302)
            self.assertTrue(good.url.endswith('/dashboard/'))
            owner.refresh_from_db()
            self.assertTrue(owner.is_active)
            self.assertFalse(PlatformControl.get_solo().maintenance_mode)

            unlocked = self.client.get('/')
            self.assertEqual(unlocked.status_code, 200)
