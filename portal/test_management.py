import os
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import Company, CompanyMembership, IntegrationCredential
from .tenancy import decrypt_secret, encrypt_secret, verify_company_pin

User = get_user_model()


class MultiCompanyManagementTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('tenantowner', 'owner@example.com', 'strong-password-123')
        self.member = User.objects.create_user('tenantmember', 'member@example.com', 'strong-password-123')
        self.company_pin = 'CRETAN-TEST-8241'
        self.company = Company.objects.create(
            name='Example Company', slug='example-company',
            pin_hash=__import__('django.contrib.auth.hashers', fromlist=['make_password']).make_password(self.company_pin),
            created_by=self.owner,
        )
        CompanyMembership.objects.create(user=self.owner, company=self.company, role='company_owner')

    def test_company_pin_is_verified_against_hash(self):
        self.assertNotEqual(self.company.pin_hash, self.company_pin)
        self.assertTrue(verify_company_pin(self.company, self.company_pin))
        self.assertFalse(verify_company_pin(self.company, 'WRONG-PIN'))

    def test_company_owner_can_open_user_management(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('company_users'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Example Company users')

    def test_nonmember_cannot_view_another_company_users(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('company_users'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('management_home'))

    def test_support_group_is_blocked_from_tax_documents(self):
        support_group, _ = Group.objects.get_or_create(name='support_user')
        self.member.groups.add(support_group)
        CompanyMembership.objects.create(user=self.member, company=self.company, role='employee')
        self.client.force_login(self.member)
        response = self.client.get(reverse('tax_documents'))
        self.assertEqual(response.status_code, 403)

    def test_integration_secret_is_encrypted_and_round_trips(self):
        key = Fernet.generate_key().decode('ascii')
        with patch.dict(os.environ, {'CREDENTIAL_ENCRYPTION_KEY': key}):
            token = 'example-secret-token-not-for-production'
            ciphertext = encrypt_secret(token)
            self.assertNotEqual(ciphertext, token)
            self.assertNotIn(token, ciphertext)
            self.assertEqual(decrypt_secret(ciphertext), token)

    def test_support_ticket_page_is_available_to_company_members(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('support_tickets'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'New support request')
