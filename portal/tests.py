from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

class SignupTests(TestCase):
    def test_candidate_can_sign_up_and_reaches_dashboard(self):
        response = self.client.post(reverse('signup'), {
            'username':'newcandidate', 'email':'candidate@example.com',
            'role':'candidate', 'password1':'a-long-password-123',
            'password2':'a-long-password-123',
        })
        self.assertRedirects(response, reverse('dashboard'))
        user = User.objects.get(username='newcandidate')
        self.assertTrue(user.is_active)
        self.assertTrue(user.groups.filter(name='candidate').exists())

    def test_client_signup_requires_approval(self):
        response = self.client.post(reverse('signup'), {
            'username':'newclient', 'email':'client@example.com',
            'role':'client', 'password1':'a-long-password-123',
            'password2':'a-long-password-123',
        })
        self.assertRedirects(response, reverse('login'))
        self.assertFalse(User.objects.get(username='newclient').is_active)

    def test_public_signup_cannot_create_admin(self):
        response = self.client.post(reverse('signup'), {
            'username':'badrole', 'email':'bad@example.com',
            'role':'admin', 'password1':'a-long-password-123',
            'password2':'a-long-password-123',
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
