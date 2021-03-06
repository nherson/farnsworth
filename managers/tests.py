"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from datetime import datetime

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.utils import override_settings

from base.models import UserProfile, ProfileRequest
from utils.funcs import convert_to_url
from utils.variables import ANONYMOUS_USERNAME, MESSAGES
from managers.models import Manager, RequestType, Request, Response, Announcement

class TestPermissions(TestCase):
    def setUp(self):
        self.u = User.objects.create_user(username="u", password="pwd")
        self.st = User.objects.create_user(username="st", password="pwd")
        self.pu = User.objects.create_user(username="pu", password="pwd")
        self.su = User.objects.create_user(username="su", password="pwd")
        self.np = User.objects.create_user(username="np", password="pwd")

        self.st.is_staff = True
        self.su.is_staff, self.su.is_superuser = True, True

        self.u.save()
        self.st.save()
        self.pu.save()
        self.su.save()
        self.np.save()

        self.m = Manager.objects.create(
            title="House President",
            incumbent=UserProfile.objects.get(user=self.pu),
            president=True,
            )

        self.rt = RequestType.objects.create(
            name="Food",
            )
        self.rt.managers = [self.m]
        self.rt.save()

        self.a = Announcement.objects.create(
            manager=self.m,
            incumbent=self.m.incumbent,
            body="Test Announcement Body",
            post_date=datetime.now(),
            )

        self.request = Request.objects.create(
            owner=UserProfile.objects.get(user=self.u),
            body="request body", request_type=self.rt,
            )

        UserProfile.objects.get(user=self.np).delete()
        self.pr = ProfileRequest.objects.create(
            username="pr",
            email="pr@email.com",
            affiliation=UserProfile.STATUS_CHOICES[0][0],
            )

    def _admin_required(self, url, success_target=None):
        response = self.client.get(url)
        self.assertRedirects(response, "/login/?next=" + url)

        self.client.login(username="np", password="pwd")
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse("external"))
        self.assertContains(response, MESSAGES["NO_PROFILE"])
        self.client.logout()

        self.client.login(username="u", password="pwd")
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse("homepage"))
        self.assertContains(response, MESSAGES["ADMINS_ONLY"])
        self.client.logout()

        self.client.login(username="st", password="pwd")
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse("homepage"))
        self.assertContains(response, MESSAGES["ADMINS_ONLY"])
        self.client.logout()

        self.client.login(username="su", password="pwd")
        response = self.client.get(url)
        if success_target is None:
            self.assertEqual(response.status_code, 200)
        else:
            self.assertRedirects(response, success_target)
        self.client.logout()

    def _president_admin_required(self, url, success_target=None):
        response = self.client.get(url)
        self.assertRedirects(response, "/login/?next=" + url)

        self.client.login(username="np", password="pwd")
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse("external"))
        self.assertContains(response, MESSAGES["NO_PROFILE"])
        self.client.logout()

        self.client.login(username="u", password="pwd")
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse("homepage"))
        self.assertContains(response, MESSAGES["PRESIDENTS_ONLY"])
        self.client.logout()

        self.client.login(username="st", password="pwd")
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse("homepage"))
        self.assertContains(response, MESSAGES["PRESIDENTS_ONLY"])
        self.client.logout()

        self.client.login(username="su", password="pwd")
        response = self.client.get(url)
        if success_target is None:
            self.assertEqual(response.status_code, 200)
        else:
            self.assertRedirects(response, success_target)
        self.client.logout()

        self.client.login(username="pu", password="pwd")
        response = self.client.get(url)
        if success_target is None:
            self.assertEqual(response.status_code, 200)
        else:
            self.assertRedirects(response, success_target)
        self.client.logout()

    def _profile_required(self, url, success_target=None):
        response = self.client.get(url)
        self.assertRedirects(response, "/login/?next=" + url)

        self.client.login(username="np", password="pwd")
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse("external"))
        self.assertContains(response, MESSAGES["NO_PROFILE"])
        self.client.logout()

        self.client.login(username="u", password="pwd")
        response = self.client.get(url, follow=True)
        if success_target is None:
            self.assertEqual(response.status_code, 200)
        else:
            self.assertRedirects(response, success_target)
        self.client.logout()

        self.client.login(username="st", password="pwd")
        response = self.client.get(url, follow=True)
        if success_target is None:
            self.assertEqual(response.status_code, 200)
        else:
            self.assertRedirects(response, success_target)
        self.client.logout()

        self.client.login(username="su", password="pwd")
        response = self.client.get(url, follow=True)
        if success_target is None:
            self.assertEqual(response.status_code, 200)
        else:
            self.assertRedirects(response, success_target)
        self.client.logout()

    def test_admin_required(self):
        pages = [
            "profile_requests",
            "profile_requests/{0}".format(self.pr.pk),
            "manage_users",
            "manage_user/{0}".format(self.u.username),
            "add_user",
            "utilities",
            ]
        for page in pages:
            self._admin_required("/custom_admin/" + page + "/")
        utilities = reverse("utilities")
        self._admin_required(reverse("recount"), success_target=utilities)
        self._admin_required(reverse("managers:anonymous_login"),
                             success_target="/")
        self._admin_required(reverse("managers:end_anonymous_session"),
                             success_target=utilities)

    def test_president_admin_required(self):
        pages = [
            "managers",
            "managers/{0}".format(self.m.url_title),
            "add_manager",
            "request_types",
            "request_types/{0}".format(self.rt.url_name),
            "add_request_type",
            ]
        for page in pages:
            self._president_admin_required("/custom_admin/" + page + "/")

    def test_profile_required(self):
        pages = [
            "manager_directory",
            "manager_directory/{0}".format(self.m.url_title),
            "profile/{0}/requests".format(self.u.username),
            "requests/{0}".format(self.rt.url_name),
            "archives/all_requests",
            "requests/{0}/all".format(self.rt.url_name),
            "my_requests",
            "request/{0}".format(self.request.pk),
            "announcements",
            "announcements/{0}".format(self.a.pk),
            "announcements/{0}/edit".format(self.a.pk),
            "announcements/all",
            ]
        for page in pages:
            self._profile_required("/" + page + "/")

class TestAnonymousUser(TestCase):
    def setUp(self):
        self.u = User.objects.create_user(username="u", password="pwd")
        self.su = User.objects.create_user(username="su", password="pwd")

        self.su.is_staff, self.su.is_superuser = True, True
        self.su.save()

        self.client.login(username="su", password="pwd")

    def test_anonymous_start(self):
        response = self.client.get(reverse("homepage"))
        self.assertNotContains(
            response,
            "Logged in as anonymous user Anonymous Coward",
            )

        url = reverse("managers:anonymous_login")
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, "/")
        self.assertContains(
            response,
            "Logged in as anonymous user Anonymous Coward",
            )

    def test_anonymous_end(self):
        url = reverse("managers:anonymous_login")
        self.client.get(url)
        self.client.login(username="su", password="pwd")

        url = reverse("managers:end_anonymous_session")
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse("utilities"))
        self.assertContains(response, MESSAGES["ANONYMOUS_SESSION_ENDED"])
        self.assertNotContains(
            response,
            "Logged in as anonymous user Anonymous Coward",
            )

    def test_anonymous_profile(self):
        # Failing before anonymous user is first logged in
        url = reverse("member_profile", kwargs={"targetUsername": ANONYMOUS_USERNAME})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        url = reverse("managers:anonymous_login")
        self.client.get(url)

        url = reverse("member_profile", kwargs={"targetUsername": ANONYMOUS_USERNAME})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Anonymous Coward")

        url = reverse("my_profile")
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse("homepage"))
        self.assertContains(response, MESSAGES['SPINELESS'])

    def test_anonymous_edit_profile(self):
        # Failing before anonymous user is first logged in
        url = reverse("custom_modify_user", kwargs={"targetUsername": ANONYMOUS_USERNAME})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        url = reverse("managers:anonymous_login")
        self.client.get(url)

        url = reverse("logout")
        self.client.get(url, follow=True)

        self.client.login(username="su", password="pwd")

        url = reverse("custom_modify_user", kwargs={"targetUsername": ANONYMOUS_USERNAME})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Anonymous")
        self.assertContains(response, "Coward")
        self.assertContains(response, MESSAGES['ANONYMOUS_EDIT'])

    def test_anonymous_logout(self):
        url = reverse("managers:anonymous_login")
        self.client.get(url)

        url = reverse("logout")
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse("homepage"))
        self.assertContains(response, MESSAGES['ANONYMOUS_DENIED'])

    def test_anonymous_user_login_logout(self):
        url = reverse("managers:anonymous_login")
        self.client.get(url)

        # Need to be careful here, client.login and client.logout clear the
        # session cookies, causing this test to break
        url = reverse("login")
        response = self.client.post(url, {
                "username_or_email": "u",
                "password": "pwd",
                }, follow=True)

        self.assertRedirects(response, reverse("homepage"))
        self.assertNotContains(
            response,
            "Logged in as anonymous user Anonymous Coward",
            )

        url = reverse("logout")
        response = self.client.get(url, follow=True)
        self.assertRedirects(response, reverse("homepage"))

        response = self.client.get(reverse("homepage"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Logged in as anonymous user Anonymous Coward",
            )

class TestRequestPages(TestCase):
    def setUp(self):
        self.u = User.objects.create_user(username="u", password="pwd")
        self.pu = User.objects.create_user(username="pu", password="pwd")

        self.u.save()
        self.pu.save()

        self.m = Manager.objects.create(
            title="House President",
            president=True,
            incumbent=UserProfile.objects.get(user=self.pu)
            )

        self.rt = RequestType.objects.create(
            name="Food",
            )
        self.rt.managers = [self.m]
        self.rt.save()

        self.request = Request.objects.create(
            owner=UserProfile.objects.get(user=self.u),
            body="Request Body",
            request_type=self.rt,
            )

        self.response = Response.objects.create(
            owner=UserProfile.objects.get(user=self.pu),
            body="Response Body",
            request=self.request,
            manager=True,
            )

    def test_request_form(self):
        urls = [
            reverse("managers:view_request", kwargs={"request_pk": self.request.pk}),
            reverse("managers:requests", kwargs={"requestType": self.rt.url_name}),
            ]

        self.client.login(username="u", password="pwd")
        for url in urls + [reverse("managers:my_requests")]:
            response = self.client.get(url)
            self.assertContains(response, "Request Body")
            self.assertContains(response, "Response Body")
            self.assertNotContains(response, "Status of this request.")

        self.client.logout()
        self.client.login(username="pu", password="pwd")

        for url in urls:
            response = self.client.get(url)
            self.assertContains(response, "Request Body")
            self.assertContains(response, "Response Body")

        response = self.client.get(reverse("managers:my_requests"))
        self.assertNotContains(response, "Request Body")
        self.assertNotContains(response, "Response Body")
        self.assertNotContains(response, "Status of this request.")

class TestManager(TestCase):
    def setUp(self):
        self.su = User.objects.create_user(username="su", password="pwd")
        self.su.is_staff, self.su.is_superuser = True, True
        self.su.save()

        self.m1 = Manager.objects.create(
            title="setUp Manager",
            incumbent=UserProfile.objects.get(user=self.su),
            )

        self.m2 = Manager.objects.create(
            title="Testing Manager",
            incumbent=UserProfile.objects.get(user=self.su),
            )

        self.client.login(username="su", password="pwd")

    def test_add_manager(self):
        url = reverse("managers:add_manager")
        response = self.client.post(url, {
            "title": "Test Manager",
            "incumbent": "1",
            "compensation": "Test % Compensation",
            "duties": "Testing Add Managers Page",
            "email": "tester@email.com",
            "president": False,
            "workshift_manager": False,
            "active": True,
            "semester_hours": 5,
            "summer_hours": 5,
            "update_manager": "",
            }, follow=True)
        self.assertRedirects(response, url)
        self.assertContains(
            response,
            MESSAGES['MANAGER_ADDED'].format(managerTitle="Test Manager"),
            )
        self.assertEqual(1, Manager.objects.filter(title="Test Manager").count())
        self.assertEqual(1, Manager.objects.filter(url_title=convert_to_url("Test Manager")).count())

    def test_duplicate_title(self):
        url = reverse("managers:add_manager")
        response = self.client.post(url, {
            "title": self.m1.title,
            "incumbent": "1",
            "compensation": "Test % Compensation",
            "duties": "Testing Add Managers Page",
            "email": "tester@email.com",
            "president": False,
            "workshift_manager": False,
            "active": True,
            "update_manager": "",
            })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A manager with this title already exists.")

    def test_duplicate_url_title(self):
        url = reverse("managers:add_manager")
        response = self.client.post(url, {
            "title": "SETUP MANAGER",
            "incumbent": "1",
            "compensation": "Test % Compensation",
            "duties": "Testing Add Managers Page",
            "email": "tester@email.com",
            "president": False,
            "workshift_manager": False,
            "active": True,
            "update_manager": "",
            })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This manager title maps to a url that is already taken.  Please note, "Site Admin" and "sITe_adMIN" map to the same URL.'.replace('"', "&quot;"))

    def test_edit_manager(self):
        new_title = "New setUp Manager"
        url = reverse("managers:edit_manager", kwargs={"managerTitle": self.m1.url_title})
        response = self.client.post(url, {
            "title": new_title,
            "incumbent": self.m1.incumbent.pk,
            "compensation": "Test % Compensation",
            "duties": "Testing Add Managers Page",
            "email": "tester@email.com",
            "president": False,
            "workshift_manager": False,
            "active": True,
            "semester_hours": 5,
            "summer_hours": 5,
            "update_manager": "",
            }, follow=True)
        self.assertRedirects(response, reverse("managers:meta_manager"))
        self.assertContains(
            response,
            MESSAGES['MANAGER_SAVED'].format(managerTitle=new_title),
            )
        self.assertEqual(1, Manager.objects.filter(title=new_title).count())
        self.assertEqual(1, Manager.objects.filter(url_title=convert_to_url(new_title)).count())

    def test_edit_title(self):
        url = reverse("managers:edit_manager", kwargs={"managerTitle": self.m1.url_title})
        response = self.client.post(url, {
            "title": self.m2.title,
            "incumbent": self.m2.incumbent.pk,
            "compensation": "Test % Compensation",
            "duties": "Testing Add Managers Page",
            "email": "tester@email.com",
            "president": False,
            "workshift_manager": False,
            "active": True,
            "update_manager": "",
            }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A manager with this title already exists.")

    def test_edit_url_title(self):
        url = reverse("managers:edit_manager", kwargs={"managerTitle": self.m1.url_title})
        response = self.client.post(url, {
            "title": self.m2.url_title.upper(),
            "incumbent": self.m2.incumbent.pk,
            "compensation": "Test % Compensation",
            "duties": "Testing Add Managers Page",
            "email": "tester@email.com",
            "president": False,
            "workshift_manager": False,
            "active": True,
            "update_manager": "",
            }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This manager title maps to a url that is already taken.  Please note, "Site Admin" and "sITe_adMIN" map to the same URL.'.replace('"', "&quot;"))

class TestRequestTypes(TestCase):
    def setUp(self):
        self.su = User.objects.create_user(username="su", password="pwd")
        self.su.is_staff, self.su.is_superuser = True, True
        self.su.save()

        self.m1 = Manager.objects.create(
            title="setUp Manager",
            incumbent=UserProfile.objects.get(user=self.su),
            )

        self.m2 = Manager.objects.create(
            title="Testing Manager",
            incumbent=UserProfile.objects.get(user=self.su),
            )

        self.rt = RequestType.objects.create(
            name="Super",
            )
        self.rt.managers = [self.m1, self.m2]
        self.rt.save()

        self.rt2 = RequestType.objects.create(
            name="Duper",
            )

        self.client.login(username="su", password="pwd")

    def test_manage_view(self):
        url = reverse("managers:manage_request_types")
        response = self.client.get(url)
        self.assertContains(response, self.rt.name)
        self.assertContains(response, self.rt.url_name)
        self.assertContains(response, self.m1.title)
        self.assertContains(response, self.m1.url_title)
        self.assertContains(response, self.m2.title)
        self.assertContains(response, self.m2.url_title)

    def test_add_request(self):
        name = "Cleanliness"
        url = reverse("managers:add_request_type")
        response = self.client.post(url, {
            "name": name,
            "managers": [self.m1.pk, self.m2.pk],
            }, follow=True)
        self.assertRedirects(response, reverse("managers:manage_request_types"))
        self.assertContains(response,
                            MESSAGES['REQUEST_TYPE_ADDED'].format(typeName=name))
        rt = RequestType.objects.get(name=name)
        self.assertIn(self.m1, rt.managers.all())
        self.assertIn(self.m2, rt.managers.all())

    def test_edit_request(self):
        url = reverse("managers:edit_request_type", kwargs={"typeName": self.rt.url_name})
        response = self.client.post(url, {
            "name": "New Name",
            "managers": [self.m2.pk],
            "enabled": False,
            })

        self.assertRedirects(response, reverse("managers:manage_request_types"))

        rt = RequestType.objects.get(pk=self.rt.pk)
        self.assertNotIn(self.m1, rt.managers.all())
        self.assertIn(self.m2, rt.managers.all())
        self.assertEqual(rt.enabled, False)
        self.assertEqual(rt.name, "New Name")
        self.assertEqual(rt.url_name, "new_name")

    def test_add_duplicate_name(self):
        url = reverse("managers:add_request_type")
        response = self.client.post(url, {
            "name": self.rt.name,
            })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A request type with this name already exists.")

    def test_edit_duplicate_name(self):
        url = reverse("managers:edit_request_type", kwargs={"typeName": self.rt2.url_name})
        response = self.client.post(url, {
            "name": self.rt.name,
            "managers": [self.m2.pk],
            })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A request type with this name already exists.")

    def test_add_duplicate_url_name(self):
        url = reverse("managers:add_request_type")
        response = self.client.post(url, {
            "name": self.rt.name.upper(),
            })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This request type name maps to a url that is already taken.  Please note, "Waste Reduction" and "wasTE_RedUCtiON" map to the same URL.'.replace('"', "&quot;"))

    def test_edit_duplicate_url_name(self):
        url = reverse("managers:edit_request_type", kwargs={"typeName": self.rt2.url_name})
        response = self.client.post(url, {
            "name": self.rt.name.upper(),
            "managers": [self.m2.pk],
            })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This request type name maps to a url that is already taken.  Please note, "Waste Reduction" and "wasTE_RedUCtiON" map to the same URL.'.replace('"', "&quot;"))

class TestAnnouncements(TestCase):
    def setUp(self):
        self.u = User.objects.create_user(username="u", password="pwd")
        self.ou = User.objects.create_user(username="ou", password="pwd")
        self.su = User.objects.create_user(username="su", password="pwd")

        self.su.is_staff, self.su.is_superuser = True, True
        self.su.save()

        self.m = Manager.objects.create(
            title="setUp Manager",
            incumbent=UserProfile.objects.get(user=self.u),
            )

        self.a = Announcement.objects.create(
            manager=self.m,
            incumbent=self.m.incumbent,
            body="Test Announcement Body",
            post_date=datetime.now(),
            )

        self.client.login(username="u", password="pwd")

    def test_announcements(self):
        url = reverse("managers:announcements")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.a.body)

    def test_individual(self):
        url = reverse("managers:view_announcement", kwargs={"announcement_pk": self.a.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.a.body)

    def test_edit_announcement(self):
        url = reverse("managers:edit_announcement", kwargs={"announcement_pk": self.a.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.a.body)

        new_body = "New Test Announcement Body"
        response = self.client.post(url, {
            "body": new_body,
            "manager": self.a.manager.pk,
            }, follow=True)

        url = reverse("managers:view_announcement", kwargs={"announcement_pk": self.a.pk})
        self.assertRedirects(response, url)
        self.assertContains(response, new_body)

        self.assertEqual(new_body, Announcement.objects.get(pk=self.a.pk).body)

    @override_settings(ANNOUNCEMENT_LIFE=0)
    def test_unpin(self):
        self.a.pinned = True
        self.a.save()

        url = reverse("managers:announcements")
        response = self.client.post(url, {
            "unpin-{0}-pk": True,
            }, follow=True)

        self.assertRedirects(response, url)
        self.assertNotContains(response, self.a.body)

    def test_no_edit(self):
        self.client.logout()
        self.client.login(username="ou", password="pwd")

        url = reverse("managers:edit_announcement", kwargs={"announcement_pk": self.a.pk})
        response = self.client.get(url)

        url = reverse("managers:view_announcement", kwargs={"announcement_pk": self.a.pk})
        self.assertRedirects(response, url)

        self.client.logout()
        self.client.login(username="su", password="pwd")

        url = reverse("managers:edit_announcement", kwargs={"announcement_pk": self.a.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

    @override_settings(ANNOUNCEMENT_LIFE=0)
    def test_unpin_individual(self):
        self.a.pinned = True
        self.a.save()

        url = reverse("managers:view_announcement", kwargs={"announcement_pk": self.a.pk})
        response = self.client.post(url, {
            "pin": False,
            }, follow=True)
        self.assertRedirects(response, url)
        self.assertContains(response, self.a.body)

        response = self.client.get(reverse("managers:announcements"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.a.body)

class TestPreFill(TestCase):
    def test_pre_fill(self):
        from farnsworth.pre_fill import main, REQUESTS, MANAGERS
        main([])
        for title in [i[0] for i in MANAGERS]:
            self.assertEqual(1, Manager.objects.filter(title=title).count())
        for name in [i[0] for i in REQUESTS]:
            self.assertEqual(1, RequestType.objects.filter(name=name).count())
