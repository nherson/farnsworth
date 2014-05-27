from smtplib import SMTPException
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout, login, authenticate, hashers
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.core.mail import send_mail
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, render, get_object_or_404
from django.template import RequestContext
from django.utils.timezone import utc

from datetime import datetime, timedelta

from social.apps.django_app.default.models import UserSocialAuth

from farnsworth.settings import house, short_house, ADMINS, max_threads, max_messages, \
    home_max_announcements, home_max_threads, SEND_EMAILS, EMAIL_HOST_USER, \
    EMAIL_BLACKLIST
from utils.variables import ANONYMOUS_USERNAME, MESSAGES, APPROVAL_SUBJECT, \
	APPROVAL_EMAIL, DELETION_SUBJECT, DELETION_EMAIL, SUBMISSION_SUBJECT, \
	SUBMISSION_EMAIL
from base.models import UserProfile, ProfileRequest
from base.redirects import red_ext, red_home
from base.decorators import profile_required, admin_required
from base.forms import ProfileRequestForm, AddUserForm, ModifyUserForm, \
    ModifyProfileRequestForm, ChangeUserPasswordForm, LoginForm, ChangePasswordForm, \
    UpdateProfileForm, DeleteUserForm
from threads.models import Thread, Message
from threads.forms import ThreadForm, MessageForm
from managers.models import RequestType, Manager, Request, Response, Announcement
from managers.forms import AnnouncementForm, ManagerResponseForm, VoteForm, UnpinForm
from events.models import Event
from events.forms import RsvpForm

def add_context(request):
	''' Add variables to all dictionaries passed to templates. '''
	PRESIDENT = False # whether the user has president privileges
	try:
		userProfile = UserProfile.objects.get(user=request.user)
	except (UserProfile.DoesNotExist, TypeError):
		pass
	else:
		for pos in Manager.objects.filter(incumbent=userProfile):
			if pos.president:
				PRESIDENT = True
				break
	if request.user.username == ANONYMOUS_USERNAME:
		request.session['ANONYMOUS_SESSION'] = True
	ANONYMOUS_SESSION = request.session.get('ANONYMOUS_SESSION', False)
	request_types = list() # A list with items of form (RequestType, number_of_open_requests)
	for request_type in RequestType.objects.filter(enabled=True):
		request_types.append((request_type, Request.objects.filter(request_type=request_type, filled=False, closed=False).count()))
	return {
		'REQUEST_TYPES': request_types,
		'HOUSE': house,
		'ANONYMOUS_USERNAME':ANONYMOUS_USERNAME,
		'SHORT_HOUSE': short_house,
		'ADMIN': ADMINS[0],
		'NUM_OF_PROFILE_REQUESTS': ProfileRequest.objects.all().count(),
		'ANONYMOUS_SESSION': ANONYMOUS_SESSION,
		'PRESIDENT': PRESIDENT,
		}

def landing_view(request):
	''' The external landing.'''
	return render_to_response('external.html', {
			'page_name': "Landing",
			}, context_instance=RequestContext(request))

@profile_required(redirect_no_user='external', redirect_profile=red_ext)
def homepage_view(request, message=None):
	''' The view of the homepage. '''
	userProfile = UserProfile.objects.get(user=request.user)
	request_types = RequestType.objects.filter(enabled=True)
	manager_request_types = list() # List of request types for which the user is a relevant manager
	for request_type in request_types:
		for position in request_type.managers.filter(active=True):
			if userProfile == position.incumbent:
				manager_request_types.append(request_type)
				break
	requests_dict = list() # Pseudo-dictionary, list with items of form (request_type, (request, [list_of_request_responses], response_form))
	# Generate a dict of unfilled, unclosed requests for each request_type for which the user is a relevant manager:
	if manager_request_types:
		for request_type in manager_request_types:
			requests_list = list() # Items of form (request, [list_of_request_responses], response_form, upvote, vote_form)
			# Select only unclosed, unfilled requests of type request_type:
			type_requests = Request.objects.filter(request_type=request_type, filled=False, closed=False)
			for req in type_requests:
				response_list = Response.objects.filter(request=req)
				form = ManagerResponseForm(initial={'request_pk': req.pk})
				upvote = userProfile in req.upvotes.all()
				vote_form = VoteForm(initial={'request_pk': req.pk})
				requests_list.append((req, response_list, form, upvote, vote_form))
			requests_dict.append((request_type, requests_list))
	announcement_form = None
	manager_positions = Manager.objects.filter(incumbent=userProfile)
	if manager_positions:
		announcement_form = AnnouncementForm(manager_positions)
	announcements_dict = list() # Pseudo-dictionary, list with items of form (announcement, announcement_unpin_form)
	announcements = Announcement.objects.filter(pinned=True)
	x = 0 # Number of announcements loaded
	for a in announcements:
		unpin_form = None
		if (a.manager.incumbent == userProfile) or request.user.is_superuser:
			unpin_form = UnpinForm(initial={'announcement_pk': a.pk})
		announcements_dict.append((a, unpin_form))
		x += 1
		if x >= home_max_announcements:
			break
	now = datetime.utcnow().replace(tzinfo=utc)
	tomorrow = now + timedelta(hours=24)
	# Get only next 24 hours of events:
	events_list = Event.objects.all().exclude(start_time__gte=tomorrow).exclude(end_time__lte=now)
	events_dict = list() # Pseudo-dictionary, list with items of form (event, ongoing, rsvpd, rsvp_form)
	for event in events_list:
		form = RsvpForm(initial={'event_pk': event.pk})
		ongoing = ((event.start_time <= now) and (event.end_time >= now))
		rsvpd = (userProfile in event.rsvps.all())
		events_dict.append((event, ongoing, rsvpd, form))
	thread_form = ThreadForm()
	threads = list() # List of recent threads
	x = 0
	for thread in Thread.objects.all():
		threads.append(thread)
		x += 1
		if x >= home_max_threads:
			break
	if request.method == 'POST':
		if 'add_response' in request.POST:
			response_form = ManagerResponseForm(request.POST)
			if response_form.is_valid():
				request_pk = response_form.cleaned_data['request_pk']
				body = response_form.cleaned_data['body']
				relevant_request = Request.objects.get(pk=request_pk)
				new_response = Response(owner=userProfile, body=body, request=relevant_request)
				relevant_request.closed = response_form.cleaned_data['mark_closed']
				relevant_request.filled = response_form.cleaned_data['mark_filled']
				new_response.manager = True
				relevant_request.change_date = datetime.utcnow().replace(tzinfo=utc)
				relevant_request.number_of_responses += 1
				relevant_request.save()
				new_response.save()
				if relevant_request.closed:
					messages.add_message(request, messages.SUCCESS, MESSAGES['REQ_CLOSED'])
				if relevant_request.filled:
					messages.add_message(request, messages.SUCCESS, MESSAGES['REQ_FILLED'])
				return HttpResponseRedirect(reverse('homepage'))
			else:
				messages.add_message(request, messages.ERROR, MESSAGES['INVALID_FORM'])
		elif 'post_announcement' in request.POST:
			announcement_form = AnnouncementForm(manager_positions, post=request.POST)
			if announcement_form.is_valid():
				body = announcement_form.cleaned_data['body']
				manager = announcement_form.cleaned_data['as_manager']
				new_announcement = Announcement(manager=manager, body=body, incumbent=userProfile, pinned=True)
				new_announcement.save()
				return HttpResponseRedirect(reverse('homepage'))
			else:
				messages.add_message(request, messages.ERROR, MESSAGES['INVALID_FORM'])
		elif 'unpin' in request.POST:
			unpin_form = UnpinForm(request.POST)
			if unpin_form.is_valid():
				announcement_pk = unpin_form.cleaned_data['announcement_pk']
				relevant_announcement = Announcement.objects.get(pk=announcement_pk)
				relevant_announcement.pinned = False
				relevant_announcement.save()
				return HttpResponseRedirect(reverse('homepage'))
			else:
				messages.add_message(request, messages.ERROR, MESSAGES['INVALID_FORM'])
		elif 'rsvp' in request.POST:
			rsvp_form = RsvpForm(request.POST)
			if rsvp_form.is_valid():
				event_pk = rsvp_form.cleaned_data['event_pk']
				relevant_event = Event.objects.get(pk=event_pk)
				if userProfile in relevant_event.rsvps.all():
					relevant_event.rsvps.remove(userProfile)
					message = MESSAGES['RSVP_REMOVE'].format(event=relevant_event.title)
					messages.add_message(request, messages.SUCCESS, message)
				else:
					relevant_event.rsvps.add(userProfile)
					message = MESSAGES['RSVP_ADD'].format(event=relevant_event.title)
					messages.add_message(request, messages.SUCCESS, message)
				relevant_event.save()
				return HttpResponseRedirect(reverse('homepage'))
			else:
				messages.add_message(request, messages.ERROR, MESSAGES['INVALID_FORM'])
		elif 'submit_thread_form' in request.POST:
			thread_form = ThreadForm(request.POST)
			if thread_form.is_valid():
				subject = thread_form.cleaned_data['subject']
				body = thread_form.cleaned_data['body']
				thread = Thread(owner=userProfile, subject=subject, number_of_messages=1, active=True)
				thread.save()
				message = Message(body=body, owner=userProfile, thread=thread)
				message.save()
				return HttpResponseRedirect(reverse('homepage'))
			else:
				messages.add_message(request, messages.ERROR, MESSAGES['THREAD_ERROR'])
		elif 'upvote' in request.POST:
			vote_form = VoteForm(request.POST)
			if vote_form.is_valid():
				request_pk = vote_form.cleaned_data['request_pk']
				relevant_request = Request.objects.get(pk=request_pk)
				if userProfile in relevant_request.upvotes.all():
					relevant_request.upvotes.remove(userProfile)
				else:
					relevant_request.upvotes.add(userProfile)
				relevant_request.save()
				return HttpResponseRedirect(reverse('homepage'))
			else:
				messages.add_message(request, messages.ERROR, MESSAGES['INVALID_FORM'])
		else:
			messages.add_message(request, messages.ERROR, MESSAGES['UNKNOWN_FORM'])
	return render_to_response('homepage.html', {
			'page_name': "Home",
			'requests_dict': requests_dict,
			'announcements_dict': announcements_dict,
			'announcement_form': announcement_form,
			'events_dict': events_dict,
			'threads': threads,
			'thread_form': thread_form,
			}, context_instance=RequestContext(request))

def help_view(request):
	''' The view of the helppage. '''
	return render_to_response('helppage.html', {
			'page_name': "Help Page",
			},  context_instance=RequestContext(request))

def site_map_view(request):
	''' The view of the site map. '''
	page_name = "Site Map"
	return render_to_response('site_map.html', {
			'page_name': page_name,
			}, context_instance=RequestContext(request))

@profile_required
def my_profile_view(request):
	''' The view of the profile page. '''
	page_name = "Profile Page"
	if request.user.username == ANONYMOUS_USERNAME:
		return red_home(request, MESSAGES['SPINELESS'])
	user = request.user
	userProfile = UserProfile.objects.get(user=request.user)
	try:
		social_auth = UserSocialAuth.objects.get(user=user)
	except UserSocialAuth.DoesNotExist:
		social_auth = None
	change_password_form = ChangePasswordForm()
	update_profile_form = UpdateProfileForm(initial={
			'current_room': userProfile.current_room,
			'former_rooms': userProfile.former_rooms,
			'former_houses': userProfile.former_houses,
			'email': user.email,
			'email_visible_to_others': userProfile.email_visible,
			'phone_number': userProfile.phone_number,
			'phone_visible_to_others': userProfile.phone_visible,
			})
	if request.method == 'POST':
		if 'submit_password_form' in request.POST:
			change_password_form = ChangePasswordForm(request.POST)
			if change_password_form.is_valid():
				current_password = change_password_form.cleaned_data['current_password']
				new_password = change_password_form.cleaned_data['new_password']
				confirm_password = change_password_form.cleaned_data['confirm_password']
				if hashers.check_password(current_password, user.password):
					hashed_password = hashers.make_password(new_password)
					if hashers.is_password_usable(hashed_password):
						user.password = hashed_password
						user.save()
						messages.add_message(request, messages.SUCCESS, "Your password was successfully changed.")
						return HttpResponseRedirect(reverse('my_profile'))
					else:
						password_non_field_error = "Password didn't hash properly.  Please try again."
						change_password_form.errors['__all__'] = change_password_form.error_class([password_non_field_error])
						return render_to_response('my_profile.html', {
								'page_name': page_name,
								'update_profile_form': update_profile_form,
								'change_password_form': change_password_form,
								}, context_instance=RequestContext(request))
				else:
					change_password_form._errors['current_password'] = forms.util.ErrorList([u"Wrong password."])
		elif 'submit_profile_form' in request.POST:
			update_profile_form = UpdateProfileForm(request.POST)
			if update_profile_form.is_valid():
				current_room = update_profile_form.cleaned_data['current_room']
				former_rooms = update_profile_form.cleaned_data['former_rooms']
				former_houses = update_profile_form.cleaned_data['former_houses']
				email = update_profile_form.cleaned_data['email']
				email_visible_to_others = update_profile_form.cleaned_data['email_visible_to_others']
				phone_number = update_profile_form.cleaned_data['phone_number']
				phone_visible_to_others = update_profile_form.cleaned_data['phone_visible_to_others']
				enter_password = update_profile_form.cleaned_data['enter_password']
				if social_auth or hashers.check_password(enter_password, user.password):
					userProfile.current_room = current_room
					userProfile.former_rooms = former_rooms
					userProfile.former_houses = former_houses
					user.email = email
					userProfile.email_visible = email_visible_to_others
					userProfile.phone_number = phone_number
					userProfile.phone_visible = phone_visible_to_others
					userProfile.save()
					messages.add_message(request, messages.SUCCESS, "Your profile has been successfully updated.")
					return HttpResponseRedirect(reverse('my_profile'))
				else:
					update_profile_form._errors['enter_password'] = forms.util.ErrorList([u"Wrong password"])
		else:
			return red_home(request, MESSAGES['UNKNOWN_FORM'])
	return render_to_response('my_profile.html', {
			'page_name': page_name,
			'update_profile_form': update_profile_form,
			'change_password_form': change_password_form,
			}, context_instance=RequestContext(request))

def login_view(request):
	''' The view of the login page. '''
	ANONYMOUS_SESSION = request.session.get('ANONYMOUS_SESSION', False)
	page_name = "Login Page"
	redirect_to = request.REQUEST.get('next', reverse('homepage'))
	if (request.user.is_authenticated() and not ANONYMOUS_SESSION) or (ANONYMOUS_SESSION and request.user.username != ANONYMOUS_USERNAME):
		return HttpResponseRedirect(redirect_to)
	form = LoginForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		username = form.cleaned_data['username']
		password = form.cleaned_data['password']
		if username == ANONYMOUS_USERNAME:
			return red_ext(request, MESSAGES['ANONYMOUS_DENIED'])
		try:
			temp_user = User.objects.get(username=username)
			if temp_user is not None:
				if temp_user.is_active:
					user = authenticate(username=username, password=password)
					if user is not None:
						login(request, user)
						if ANONYMOUS_SESSION:
							request.session['ANONYMOUS_SESSION'] = True
						return HttpResponseRedirect(redirect_to)
					else:
						form.errors['__all__'] = form.error_class(["Invalid username/password combination.  Please try again."])
				else:
					form.errors['__all__'] = form.error_class(["Your account is not active.  Please contact the site administrator to activate your account."])
		except User.DoesNotExist:
			form.errors['__all__'] = form.error_class(["Invalid username/password combination.  Please try again."])

	return render_to_response('login.html', {
			'page_name': page_name,
			'form': form,
			'oauth_providers': _get_oauth_providers(),
			'redirect_to': redirect_to,
			}, context_instance=RequestContext(request))

def _get_oauth_providers():
	matches = {
		"facebook": ("Facebook", "fb.png"),
		"google-oauth": ("Google", "google.png"),
		"google-oauth2": ("Google", "google.png"),
		"github": ("Github", "github.ico"),
		}

	providers = []
	for provider in settings.AUTHENTICATION_BACKENDS:
		if provider.startswith("social"):
			module_name, backend = provider.rsplit(".", 1)
			module = __import__(module_name, fromlist=[''])
			if module and getattr(module, backend, ""):
				backend_name = getattr(module, backend).name
				full_name, icon = matches.get(backend_name,
							      ("Unknown", "unknown.png"))
				providers.append((backend_name, full_name, icon))
	return providers

def logout_view(request):
	''' Log the user out. '''
	ANONYMOUS_SESSION = request.session.get('ANONYMOUS_SESSION', False)
	if ANONYMOUS_SESSION:
		if request.user.username != ANONYMOUS_USERNAME:
			logout(request)
			try:
				spineless = User.objects.get(username=ANONYMOUS_USERNAME)
			except User.DoesNotExist:
				random_password = User.objects.make_random_password()
				spineless = User.objects.create_user(username=ANONYMOUS_USERNAME, first_name="Anonymous", last_name="Coward", password=random_password)
				spineless.is_active = False
				spineless.save()
				spineless_profile = UserProfile.objects.get(user=spineless)
				spineless_profile.status = UserProfile.ALUMNUS
				spineless_profile.save()
			spineless.backend = 'django.contrib.auth.backends.ModelBackend'
			login(request, spineless)
			request.session['ANONYMOUS_SESSION'] = True
		else:
			messages.add_message(request, messages.ERROR, MESSAGES['ANONYMOUS_DENIED'])
	else:
		logout(request)
	return HttpResponseRedirect(reverse('homepage'))

@profile_required
def member_directory_view(request):
	''' View of member directory. '''
	page_name = "Member Directory"
	residents = UserProfile.objects.filter(status=UserProfile.RESIDENT)
	boarders = UserProfile.objects.filter(status=UserProfile.BOARDER)
	alumni = UserProfile.objects.filter(status=UserProfile.ALUMNUS) \
	    .exclude(user__username=ANONYMOUS_USERNAME)
	return render_to_response('member_directory.html', {
			'page_name': page_name,
			'residents': residents,
			'boarders': boarders,
			'alumni': alumni,
			}, context_instance=RequestContext(request))

@profile_required
def member_profile_view(request, targetUsername):
	''' View a member's Profile. '''
	if targetUsername == request.user.username and targetUsername != ANONYMOUS_USERNAME:
		return HttpResponseRedirect(reverse('my_profile'))
	page_name = "%s's Profile" % targetUsername
	userProfile = UserProfile.objects.get(user=request.user)
	targetUser = get_object_or_404(User, username=targetUsername)
	targetProfile = get_object_or_404(UserProfile, user=targetUser)
	number_of_threads = Thread.objects.filter(owner=targetProfile).count()
	number_of_requests = Request.objects.filter(owner=targetProfile).count()
	return render_to_response('member_profile.html', {
			'page_name': page_name,
			'targetUser': targetUser,
			'targetProfile': targetProfile,
			'number_of_threads': number_of_threads,
			'number_of_requests': number_of_requests,
			}, context_instance=RequestContext(request))

def request_profile_view(request):
	''' The page to request a user profile on the site. '''
	page_name = "Profile Request Page"
	redirect_to = request.REQUEST.get('next', reverse('homepage'))
	if request.user.is_authenticated() and request.user.username != ANONYMOUS_USERNAME:
		return HttpResponseRedirect(redirect_to)
	form = ProfileRequestForm(request.POST or None)
	if form.is_valid():
		username = form.cleaned_data['username']
		first_name = form.cleaned_data['first_name']
		last_name = form.cleaned_data['last_name']
		email = form.cleaned_data['email']
		affiliation = form.cleaned_data['affiliation_with_the_house']
		password = form.cleaned_data['password']
		confirm_password = form.cleaned_data['confirm_password']
		hashed_password = hashers.make_password(password)
		if User.objects.filter(username=username).count():
			form._errors['first_name'] = forms.util.ErrorList([MESSAGES["USERNAME_TAKEN"].format(username=username)])
		elif ProfileRequest.objects.filter(first_name=first_name, last_name=last_name).count():
			form.errors['__all__'] = form.error_class([MESSAGES["PROFILE_TAKEN"].format(first_name=first_name, last_name=last_name)])
		elif not hashers.is_password_usable(hashed_password):
			form.errors['__all__'] = form.error_class([MESSAGES['PASSWORD_UNHASHABLE']])
		else:
			profile_request = ProfileRequest(username=username, first_name=first_name, last_name=last_name, email=email,
				affiliation=affiliation, password=hashed_password)
			profile_request.save()
			messages.add_message(request, messages.SUCCESS, MESSAGES['PROFILE_SUBMITTED'])
			if SEND_EMAILS and (email not in EMAIL_BLACKLIST):
				submission_subject = SUBMISSION_SUBJECT.format(house=house)
				submission_email = SUBMISSION_EMAIL.format(house=house, full_name=first_name + " " + last_name, admin_name=ADMINS[0][0],
					admin_email=ADMINS[0][1])
				try:
					send_mail(submission_subject, submission_email, EMAIL_HOST_USER, [email], fail_silently=False)
					# Add logging here
				except SMTPException:
					pass # Add logging here
			return HttpResponseRedirect(redirect_to)
	return render(request, 'request_profile.html', {
			'form': form,
			'page_name': page_name,
			'oauth_providers': _get_oauth_providers(),
			'redirect_to': redirect_to,
			})

@admin_required
def manage_profile_requests_view(request):
	''' The page to manager user profile requests. '''
	page_name = "Admin - Manage Profile Requests"
	profile_requests = ProfileRequest.objects.all()
	return render_to_response(
		'manage_profile_requests.html', {
			'page_name': page_name,
			'choices': UserProfile.STATUS_CHOICES,
			'profile_requests': profile_requests
			},
		context_instance=RequestContext(request))

@admin_required
def modify_profile_request_view(request, request_pk):
	''' The page to modify a user's profile request. request_pk is the pk of the profile request. '''
	page_name = "Admin - Profile Request"
	profile_request = get_object_or_404(ProfileRequest, pk=request_pk)
	if request.method == 'POST':
		addendum = ""
		mod_form = ModifyProfileRequestForm(request.POST)
		if 'delete_request' in request.POST:
			if SEND_EMAILS and (profile_request.email not in EMAIL_BLACKLIST):
				deletion_subject = DELETION_SUBJECT.format(house=house)
				deletion_email = DELETION_EMAIL.format(house=house, full_name=profile_request.first_name + " " + profile_request.last_name,
					admin_name=ADMINS[0][0], admin_email=ADMINS[0][1])
				try:
					send_mail(deletion_subject, deletion_email, EMAIL_HOST_USER, [profile_request.email], fail_silently=False)
					addendum = MESSAGES['PROFILE_REQUEST_DELETION_EMAIL'].format(full_name=profile_request.first_name + ' ' + profile_request.last_name,
						email=profile_request.email)
				except SMTPException:
					message = MESSAGES['EMAIL_FAIL'].format(email=profile_request.email, error=e)
					messages.add_message(request, messages.ERROR, message)
			profile_request.delete()
			message = MESSAGES['PREQ_DEL'].format(first_name=profile_request.first_name, last_name=profile_request.last_name, username=profile_request.username)
			messages.add_message(request, messages.SUCCESS, message + addendum)
			return HttpResponseRedirect(reverse('manage_profile_requests'))
		elif 'add_user' in request.POST:
			if mod_form.is_valid():
				username = mod_form.cleaned_data['username']
				first_name = mod_form.cleaned_data['first_name']
				last_name = mod_form.cleaned_data['last_name']
				email = mod_form.cleaned_data['email']
				email_visible_to_others = mod_form.cleaned_data['email_visible_to_others']
				phone_number = mod_form.cleaned_data['phone_number']
				phone_visible_to_others = mod_form.cleaned_data['phone_visible_to_others']
				status = mod_form.cleaned_data['status']
				current_room = mod_form.cleaned_data['current_room']
				former_rooms = mod_form.cleaned_data['former_rooms']
				former_houses = mod_form.cleaned_data['former_houses']
				is_active = mod_form.cleaned_data['is_active']
				is_staff = mod_form.cleaned_data['is_staff']
				is_superuser = mod_form.cleaned_data['is_superuser']
				groups = mod_form.cleaned_data['groups']
				if User.objects.filter(username=username).count():
					non_field_error = "This username is taken.  Try one of %s_1 through %s_10." % (username, username)
					mod_form.errors['__all__'] = mod_form.error_class([non_field_error])
				elif User.objects.filter(first_name=first_name, last_name=last_name):
					non_field_error = "A profile for %s %s already exists with username %s." % (first_name, last_name, User.objects.get(first_name=first_name, last_name=last_name).username)
					mod_form.errors['__all__'] = mod_form.error_class([non_field_error])
				else:
					new_user = User.objects.create_user(username=username, email=email, first_name=first_name, last_name=last_name)
					new_user.password = profile_request.password
					new_user.is_active = is_active
					new_user.is_staff = is_staff
					new_user.is_superuser = is_superuser
					new_user.groups = groups
					new_user.save()

					if profile_request.provider and profile_request.uid:
						social = UserSocialAuth(
							user=new_user,
							provider = profile_request.provider,
							uid = profile_request.uid,
							)
						social.save()

					new_user_profile = UserProfile.objects.get(user=new_user)
					new_user_profile.email_visible = email_visible_to_others
					new_user_profile.phone_number = phone_number
					new_user_profile.phone_visible = phone_visible_to_others
					new_user_profile.status = status
					new_user_profile.current_room = current_room
					new_user_profile.former_rooms = former_rooms
					new_user_profile.former_houses = former_houses
					new_user_profile.save()
					if new_user.is_active and SEND_EMAILS and (email not in EMAIL_BLACKLIST):
						approval_subject = APPROVAL_SUBJECT.format(house=house)
						if profile_request.provider:
							username_bit = profile_request.provider.title()
						elif new_user.username == profile_request.username:
							username_bit = "the username and password you selected"
						else:
							username_bit = "the username %s and the password you selected" % new_user.username
						login_url = request.build_absolute_uri(reverse('login'))
						approval_email = APPROVAL_EMAIL.format(house=house, full_name=new_user.get_full_name(), admin_name=ADMINS[0][0],
							admin_email=ADMINS[0][1], login_url=login_url, username_bit=username_bit, request_date=profile_request.request_date)
						try:
							send_mail(approval_subject, approval_email, EMAIL_HOST_USER, [email], fail_silently=False)
							addendum = MESSAGES['PROFILE_REQUEST_APPROVAL_EMAIL'].format(full_name=profile_request.first_name + ' ' + profile_request.last_name,
								email=profile_request.email)
						except SMTPException as e:
							message = MESSAGES['EMAIL_FAIL'].format(email=profile_request.email, error=e)
							messages.add_message(request, messages.ERROR, message)
					profile_request.delete()
					message = MESSAGES['USER_ADDED'].format(username=username)
					messages.add_message(request, messages.SUCCESS, message + addendum)
					return HttpResponseRedirect(reverse('manage_profile_requests'))
	else:
		mod_form = ModifyProfileRequestForm(initial={
				'status': profile_request.affiliation,
				'username': profile_request.username,
				'first_name': profile_request.first_name,
				'last_name': profile_request.last_name,
				'email': profile_request.email,
				'is_active': True,
				})
	return render_to_response('modify_profile_request.html', {
			'page_name': page_name,
			'add_user_form': mod_form,
			'provider': profile_request.provider,
			'uid': profile_request.uid,
			}, context_instance=RequestContext(request))

@admin_required
def custom_manage_users_view(request):
	page_name = "Admin - Manage Users"
	residents = UserProfile.objects.filter(status=UserProfile.RESIDENT)
	boarders = UserProfile.objects.filter(status=UserProfile.BOARDER)
	alumni = UserProfile.objects.filter(status=UserProfile.ALUMNUS).exclude(user__username=ANONYMOUS_USERNAME)
	return render_to_response('custom_manage_users.html', {
			'page_name': page_name,
			'residents': residents,
			'boarders': boarders,
			'alumni': alumni,
			}, context_instance=RequestContext(request))

@admin_required
def custom_modify_user_view(request, targetUsername):
	''' The page to modify a user. '''
	if targetUsername == ANONYMOUS_USERNAME:
		messages.add_message(request, messages.WARNING, MESSAGES['ANONYMOUS_EDIT'])
	page_name = "Admin - Modify User"
	targetUser = get_object_or_404(User, username=targetUsername)
	targetProfile = get_object_or_404(UserProfile, user=targetUser)

	modify_user_form = ModifyUserForm(initial={
			'first_name': targetUser.first_name,
			'last_name': targetUser.last_name,
			'email': targetUser.email,
			'email_visible_to_others': targetProfile.email_visible,
			'phone_number': targetProfile.phone_number,
			'phone_visible_to_others': targetProfile.phone_visible,
			'status': targetProfile.status,
			'current_room': targetProfile.current_room,
			'former_rooms': targetProfile.former_rooms,
			'former_houses': targetProfile.former_houses,
			'is_active': targetUser.is_active,
			'is_staff': targetUser.is_staff,
			'is_superuser': targetUser.is_superuser,
			'groups': targetUser.groups.all(),
			})
	change_user_password_form = ChangeUserPasswordForm()
	delete_user_form = DeleteUserForm()
	thread_count = Thread.objects.filter(owner=targetProfile).count(),
	message_count = Message.objects.filter(owner=targetProfile).count(),
	request_count = Request.objects.filter(owner=targetProfile).count(),
	response_count = Response.objects.filter(owner=targetProfile).count(),
	announcement_count = Announcement.objects.filter(incumbent=targetProfile).count(),
	event_count = Event.objects.filter(owner=targetProfile).count(),
	if 'update_user_profile' in request.POST:
		modify_user_form = ModifyUserForm(request.POST)
		if modify_user_form.is_valid():
			first_name = modify_user_form.cleaned_data['first_name']
			last_name = modify_user_form.cleaned_data['last_name']
			email = modify_user_form.cleaned_data['email']
			email_visible_to_others = modify_user_form.cleaned_data['email_visible_to_others']
			phone_number = modify_user_form.cleaned_data['phone_number']
			phone_visible_to_others = modify_user_form.cleaned_data['phone_visible_to_others']
			status = modify_user_form.cleaned_data['status']
			current_room = modify_user_form.cleaned_data['current_room']
			former_rooms = modify_user_form.cleaned_data['former_rooms']
			former_houses = modify_user_form.cleaned_data['former_houses']
			is_active = modify_user_form.cleaned_data['is_active']
			is_staff = modify_user_form.cleaned_data['is_staff']
			is_superuser = modify_user_form.cleaned_data['is_superuser']
			groups = modify_user_form.cleaned_data['groups']
			targetUser.first_name = first_name
			targetUser.last_name = last_name
			targetUser.is_active = is_active
			targetUser.is_staff = is_staff
			targetUser.email = email
			if (targetUser == request.user and
			    User.objects.filter(is_superuser=True).count() <= 1 and
			    not is_superuser):
				messages.add_message(request, messages.ERROR, MESSAGES['LAST_SUPERADMIN'])
			else:
				targetUser.is_superuser = is_superuser
			targetUser.groups = groups
			targetUser.save()
			targetProfile.email_visible = email_visible_to_others
			targetProfile.phone_number = phone_number
			targetProfile.phone_visible = phone_visible_to_others
			targetProfile.status = status
			targetProfile.current_room = current_room
			targetProfile.former_rooms = former_rooms
			targetProfile.former_houses = former_houses
			targetProfile.save()
			message = MESSAGES['USER_PROFILE_SAVED'].format(username=targetUser.username)
			messages.add_message(request, messages.SUCCESS, message)
			return HttpResponseRedirect(reverse('custom_modify_user', kwargs={'targetUsername': targetUsername}))
	elif 'change_user_password' in request.POST:
		change_user_password_form = ChangeUserPasswordForm(request.POST)
		if targetUser == request.user:
			messages.add_message(request, messages.ERROR, MESSAGES['ADMIN_PASSWORD'])
		elif change_user_password_form.is_valid():
			user_password = change_user_password_form.cleaned_data['user_password']
			confirm_password = change_user_password_form.cleaned_data['confirm_password']
			hashed_password = hashers.make_password(user_password)
			if hashers.is_password_usable(hashed_password):
				targetUser.password = hashed_password
				targetUser.save()
				message = MESSAGES['USER_PW_CHANGED'].format(username=targetUser.username)
				messages.add_message(request, messages.SUCCESS, message)
				return HttpResponseRedirect(reverse('custom_modify_user', kwargs={'targetUsername': targetUsername}))
			else:
				error = "Could not hash password.  Please try again."
				change_user_password_form.errors['__all__'] = change_user_password_form.error_class([error])
	elif 'delete_user' in request.POST:
		delete_user_form = DeleteUserForm(request.POST)
		if targetUser == request.user:
			messages.add_message(request, messages.ERROR, MESSAGES['SELF_DELETE'])
		elif delete_user_form.is_valid():
			username = delete_user_form.cleaned_data['username']
			password = delete_user_form.cleaned_data['password']
			if not hashers.check_password(password, request.user.password):
				delete_user_form._errors['password'] = forms.util.ErrorList([u"Wrong password."])
			elif username == targetUsername:
				targetUser.delete()
				message = MESSAGES['USER_DELETED'].format(username=username)
				messages.add_message(request, messages.SUCCESS, message)
				return HttpResponseRedirect(reverse("custom_manage_users"))
			else:
				error = "Username incorrect."
				delete_user_form.errors['username'] = delete_user_form.error_class([error])

	return render_to_response('custom_modify_user.html', {
			'targetUser': targetUser,
			'targetProfile': targetProfile,
			'page_name': page_name,
			'modify_user_form': modify_user_form,
			'change_user_password_form': change_user_password_form,
			'delete_user_form': delete_user_form,
			'thread_count': Thread.objects.filter(owner=targetProfile).count(),
			'message_count': Message.objects.filter(owner=targetProfile).count(),
			'request_count': Request.objects.filter(owner=targetProfile).count(),
			'response_count': Response.objects.filter(owner=targetProfile).count(),
			'announcement_count': Announcement.objects.filter(incumbent=targetProfile).count(),
			'event_count': Event.objects.filter(owner=targetProfile).count(),
			}, context_instance=RequestContext(request))

@admin_required
def custom_add_user_view(request):
	''' The page to add a new user. '''
	page_name = "Admin - Add User"
	add_user_form = AddUserForm(request.POST or None, initial={
		'status': UserProfile.RESIDENT,
		})
	if add_user_form.is_valid():
		username = add_user_form.cleaned_data['username']
		first_name = add_user_form.cleaned_data['first_name']
		last_name = add_user_form.cleaned_data['last_name']
		email = add_user_form.cleaned_data['email']
		email_visible_to_others = add_user_form.cleaned_data['email_visible_to_others']
		phone_number = add_user_form.cleaned_data['phone_number']
		phone_visible_to_others = add_user_form.cleaned_data['phone_visible_to_others']
		status = add_user_form.cleaned_data['status']
		current_room = add_user_form.cleaned_data['current_room']
		former_rooms = add_user_form.cleaned_data['former_rooms']
		former_houses = add_user_form.cleaned_data['former_houses']
		is_active = add_user_form.cleaned_data['is_active']
		is_staff = add_user_form.cleaned_data['is_staff']
		is_superuser = add_user_form.cleaned_data['is_superuser']
		groups = add_user_form.cleaned_data['groups']
		user_password = add_user_form.cleaned_data['user_password']
		confirm_password = add_user_form.cleaned_data['confirm_password']
		if User.objects.filter(username=username).count():
			error = MESSAGES["USERNAME_TAKEN"].format(username=username)
			add_user_form.errors['__all__'] = add_user_form.error_class([error])
		elif User.objects.filter(first_name=first_name, last_name=last_name).count():
			non_field_error = "A profile for %s %s already exists with username %s." % (first_name, last_name, User.objects.get(first_name=first_name, last_name=last_name).username)
			add_user_form.errors['__all__'] = add_user_form.error_class([non_field_error])
		else:
			new_user = User.objects.create_user(username=username, email=email, first_name=first_name, last_name=last_name, password=user_password)
			new_user.is_active = is_active
			new_user.is_staff = is_staff
			new_user.is_superuser = is_superuser
			new_user.groups = groups
			new_user.save()
			new_user_profile = UserProfile.objects.get(user=new_user)
			new_user_profile.email_visible = email_visible_to_others
			new_user_profile.phone_number = phone_number
			new_user_profile.phone_visible = phone_visible_to_others
			new_user_profile.status = status
			new_user_profile.current_room = current_room
			new_user_profile.former_rooms = former_rooms
			new_user_profile.former_houses = former_houses
			new_user_profile.save()
			message = MESSAGES['USER_ADDED'].format(username=username)
			messages.add_message(request, messages.SUCCESS, message)
			return HttpResponseRedirect(reverse('custom_add_user'))
	return render_to_response('custom_add_user.html', {
			'page_name': page_name,
			'add_user_form': add_user_form,
			}, context_instance=RequestContext(request))

@admin_required
def utilities_view(request):
	''' View for an admin to do maintenance tasks on the site. '''
	return render_to_response('utilities.html', {
			'page_name': "Admin - Site Utilities",
			}, context_instance=RequestContext(request))
