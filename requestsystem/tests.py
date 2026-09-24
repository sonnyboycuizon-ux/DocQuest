from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from requestsystem.models import Profile


class SuspendedAccountLoginTests(TestCase):
    """
    Test suite for verifying login behavior for suspended student accounts.
    Covers all 5 required test cases from the specification.
    """

    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        self.dashboard_url = reverse('dashboard')

        self.active_student = User.objects.create_user(
            username='active_student',
            password='TestPass123!',
            first_name='Active',
            last_name='Student',
            email='active@test.edu',
            is_active=True,
            is_staff=False,
            is_superuser=False
        )
        Profile.objects.get_or_create(user=self.active_student)

        self.suspended_student = User.objects.create_user(
            username='suspended_student',
            password='TestPass123!',
            first_name='Suspended',
            last_name='Student',
            email='suspended@test.edu',
            is_active=False,
            is_staff=False,
            is_superuser=False
        )
        Profile.objects.get_or_create(user=self.suspended_student)

    def test_1_active_student_correct_credentials(self):
        """TEST 1 — ACTIVE STUDENT + CORRECT CREDENTIALS → Login successful → Dashboard"""
        response = self.client.post(self.login_url, {
            'username': 'active_student',
            'password': 'TestPass123!'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, self.dashboard_url)
        self.assertTrue('_auth_user_id' in self.client.session)

    def test_2_active_student_wrong_password(self):
        """TEST 2 — ACTIVE STUDENT + WRONG PASSWORD → 'Invalid username or password.'"""
        response = self.client.post(self.login_url, {
            'username': 'active_student',
            'password': 'WrongPass123!'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse('_auth_user_id' in self.client.session)
        messages = list(response.context.get('messages', []))
        self.assertTrue(any('Invalid username or password.' in str(m) for m in messages))

    def test_3_suspended_student_correct_password(self):
        """TEST 3 — SUSPENDED STUDENT + CORRECT PASSWORD → Suspension message, NOT logged in"""
        response = self.client.post(self.login_url, {
            'username': 'suspended_student',
            'password': 'TestPass123!'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse('_auth_user_id' in self.client.session)
        messages = list(response.context.get('messages', []))
        suspension_msgs = [str(m) for m in messages if 'suspended' in str(m).lower()]
        self.assertTrue(len(suspension_msgs) > 0,
                        "Expected suspension message, got: " + str([str(m) for m in messages]))
        invalid_msgs = [str(m) for m in messages if 'Invalid username or password' in str(m)]
        self.assertTrue(len(invalid_msgs) == 0,
                        "Should NOT show 'Invalid username or password' for correct credentials + suspended account")

    def test_4_suspended_student_wrong_password(self):
        """TEST 4 — SUSPENDED STUDENT + WRONG PASSWORD → 'Invalid username or password.'
        Must NOT reveal suspension status to someone who doesn't know the password."""
        response = self.client.post(self.login_url, {
            'username': 'suspended_student',
            'password': 'WrongPass123!'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse('_auth_user_id' in self.client.session)
        messages = list(response.context.get('messages', []))
        suspension_msgs = [str(m) for m in messages if 'suspended' in str(m).lower()]
        self.assertTrue(len(suspension_msgs) == 0,
                        "Must NOT reveal suspension when password is wrong. Got: " +
                        str([str(m) for m in messages]))
        invalid_msgs = [str(m) for m in messages if 'Invalid username or password' in str(m)]
        self.assertTrue(len(invalid_msgs) > 0,
                        "Expected 'Invalid username or password' for wrong password, got: " +
                        str([str(m) for m in messages]))

    def test_5_reactivated_student_correct_password(self):
        """TEST 5 — REACTIVATED STUDENT + CORRECT PASSWORD → Login successful → Dashboard"""
        self.suspended_student.is_active = True
        self.suspended_student.save()

        response = self.client.post(self.login_url, {
            'username': 'suspended_student',
            'password': 'TestPass123!'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, self.dashboard_url)
        self.assertTrue('_auth_user_id' in self.client.session)

    def test_nonexistent_user(self):
        """EXTRA: Non-existent username → 'Invalid username or password.'"""
        response = self.client.post(self.login_url, {
            'username': 'nonexistent_user_12345',
            'password': 'AnyPass123!'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse('_auth_user_id' in self.client.session)
        messages = list(response.context.get('messages', []))
        self.assertTrue(any('Invalid username or password.' in str(m) for m in messages))
        suspension_msgs = [str(m) for m in messages if 'suspended' in str(m).lower()]
        self.assertTrue(len(suspension_msgs) == 0,
                        "Must NOT reveal suspension for non-existent user")

    def test_admin_not_affected_by_suspension_logic(self):
        """EXTRA: Active admin can still log in normally"""
        admin_user = User.objects.create_user(
            username='test_admin',
            password='AdminPass123!',
            is_active=True,
            is_staff=True,
            is_superuser=True
        )
        Profile.objects.get_or_create(user=admin_user)

        response = self.client.post(self.login_url, {
            'username': 'test_admin',
            'password': 'AdminPass123!'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue('_auth_user_id' in self.client.session)
