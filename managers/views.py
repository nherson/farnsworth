'''
Project: Farnsworth

Author: Karandeep Singh Nagra
'''

from datetime import datetime
import re
from django.shortcuts import render_to_response, render
from django.http import HttpResponseRedirect
from django import forms
from django.core.urlresolvers import reverse
from django.contrib.auth import hashers, logout, login
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.utils.timezone import utc
from django.contrib import messages

from farnsworth.settings import house, short_house, ADMINS, max_requests, max_responses, \
    ANONYMOUS_USERNAME, MESSAGES
from models import Manager, RequestType, ProfileRequest, Request, Response, Announcement
from threads.models import UserProfile, Thread, Message
from threads.views import red_ext, red_home, UnpinForm, VoteForm, ManagerForm, RequestTypeForm
from threads.decorators import admin_required, profile_required
from managers.forms import *

def verify_username(username):
	''' Verify a potential username.
	Parameters:
		username is the potential username
	Returns True if username contains only characters a through z, A through Z, 0 through 9, or the _; returns false otherwise.
	'''
	return not bool(re.compile(r'[^a-zA-Z0-9_]').search(username))

def verify_name(name):
	''' Verify a potential first or last name.
	Parameters:
		name is the potential first or last name
	Returns True if name doesn't contain ", <, >, &, ; returns false otherwise.
	'''
	return bool(re.compile(r"[^a-zA-Z']").search(name))

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
	return {
		'REQUEST_TYPES': RequestType.objects.filter(enabled=True),
		'HOUSE': house,
		'ANONYMOUS_USERNAME':ANONYMOUS_USERNAME,
		'SHORT_HOUSE': short_house,
		'ADMIN': ADMINS[0],
		'NUM_OF_PROFILE_REQUESTS': ProfileRequest.objects.all().count(),
		'ANONYMOUS_SESSION': ANONYMOUS_SESSION,
		'PRESIDENT': PRESIDENT,
		}

def request_profile_view(request):
	''' The page to request a user profile on the site. '''
	page_name = "Profile Request Page"
	if request.user.is_authenticated():
		return HttpResponseRedirect(reverse('homepage'))
	if request.method == 'POST':
		form = ProfileRequestForm(request.POST)
		if form.is_valid():
			username = form.cleaned_data['username']
			first_name = form.cleaned_data['first_name']
			last_name = form.cleaned_data['last_name']
			email = form.cleaned_data['email']
			affiliation = form.cleaned_data['affiliation_with_the_house']
			if not verify_username(username):
				form._errors['username'] = form.error_class([u'Invalid username. Must be characters A-Z, a-z, 0-9, or "_"'])
			elif User.objects.filter(username=username).count():
				non_field_error = "This usename is taken.  Try one of %s_1 through %s_10." % (username, username)
				form.errors['__all__'] = form.error_class([non_field_error])
			else:
				profile_request = ProfileRequest(username=username, first_name=first_name, last_name=last_name, email=email, affiliation=affiliation)
				profile_request.save()
				messages.add_message(request, messages.SUCCESS, "Your request has been submitted.  An admin will contact you soon.")
				return HttpResponseRedirect(reverse('external'))
		else:
			return render(request, 'request_profile.html', {'form': form, 'page_name': page_name})
	else:
		form = ProfileRequestForm()
	return render(request, 'request_profile.html', {'form': form, 'page_name': page_name})

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
	profile_request = ProfileRequest.objects.get(pk=request_pk)
	if request.method == 'POST':
		mod_form = ModifyProfileRequestForm(request.POST)
		if 'delete_request' in request.POST:
			message = MESSAGES['PREQ_DEL'].format(first_name=profile_request.first_name, last_name=profile_request.last_name, username=profile_request.username)
			messages.add_message(request, messages.WARNING, message)
			profile_request.delete()
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
				user_password = mod_form.cleaned_data['user_password']
				confirm_password = mod_form.cleaned_data['confirm_password']
				if not verify_username(username):
					mod_form._errors['username'] = forms.util.ErrorList([u'Invalid username. Must be characters A-Z, a-z, 0-9, or "_".'])
				elif User.objects.filter(username=username).count():
					non_field_error = "This username is taken.  Try one of %s_1 through %s_10." % (username, username)
					mod_form.errors['__all__'] = mod_form.error_class([non_field_error])
				elif User.objects.filter(first_name=first_name, last_name=last_name):
					non_field_error = "A profile for %s %s already exists with username %s." % (first_name, last_name, User.objects.get(first_name=first_name, last_name=last_name).username)
					mod_form.errors['__all__'] = mod_form.error_class([non_field_error])
				elif user_password == confirm_password:
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
					profile_request.delete()
					message = MESSAGES['USER_ADDED'].format(username=username)
					messages.add_message(request, messages.SUCCESS, message)
					return HttpResponseRedirect(reverse('manage_profile_requests'))
				else:
					mod_form._errors['user_password'] = forms.util.ErrorList([u"Passwords don't match."])
					mod_form._errors['confirm_password'] = forms.util.ErrorList([u"Passwords don't match."])
	else:
		mod_form = AddUserForm(initial={'status': profile_request.affiliation, 'username': profile_request.username, 'first_name': profile_request.first_name, 'last_name': profile_request.last_name, 'email': profile_request.email})
	return render_to_response('modify_profile_request.html', {'page_name': page_name, 'add_user_form': mod_form}, context_instance=RequestContext(request))

@admin_required
def custom_manage_users_view(request):
	page_name = "Admin - Manage Users"
	residents = UserProfile.objects.filter(status=UserProfile.RESIDENT)
	boarders = UserProfile.objects.filter(status=UserProfile.BOARDER)
	alumni = UserProfile.objects.filter(status=UserProfile.ALUMNUS)
	return render_to_response('custom_manage_users.html', {'page_name': page_name, 'residents': residents, 'boarders': boarders, 'alumni': alumni}, context_instance=RequestContext(request))

@admin_required
def custom_modify_user_view(request, targetUsername):
	''' The page to modify a user. '''
	if targetUsername == ANONYMOUS_USERNAME:
		messages.add_message(request, messages.WARNING, MESSAGES['ANONYMOUS_EDIT'])
	page_name = "Admin - Modify User"
	try:
		targetUser = User.objects.get(username=targetUsername)
	except User.DoesNotExist:
		page_name = "User Not Found"
		message = "User %s does not exist or could not be found." % targetUsername
		return render_to_response('custom_modify_user.html', {'page_name': page_name, 'message': message}, context_instance=RequestContext(request))
	try:
		targetProfile = UserProfile.objects.get(user=targetUser)
	except UserProfile.DoesNotExist:
		page_name = "Profile Not Found"
		message = "Profile for user %s could not be found." % targetUsername
		return render_to_response('custom_modify_user.html', {'page_name': page_name, 'message': message}, context_instance=RequestContext(request))	
	modify_user_form = ModifyUserForm(initial={'first_name': targetUser.first_name, 'last_name': targetUser.last_name, 'email': targetUser.email, 'email_visible_to_others': targetProfile.email_visible, 'phone_number': targetProfile.phone_number, 'phone_visible_to_others': targetProfile.phone_visible, 'status': targetProfile.status, 'current_room': targetProfile.current_room, 'former_rooms': targetProfile.former_rooms, 'former_houses': targetProfile.former_houses, 'is_active': targetUser.is_active, 'is_staff': targetUser.is_staff, 'is_superuser': targetUser.is_superuser, 'groups': targetUser.groups.all()})
	change_user_password_form = ChangeUserPasswordForm()
	if request.method == 'POST':
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
				if (targetUser == request.user) and (User.objects.filter(is_superuser=True).count() <= 1):
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
			if change_user_password_form.is_valid():
				user_password = change_user_password_form.cleaned_data['user_password']
				confirm_password = change_user_password_form.cleaned_data['confirm_password']
				if user_password == confirm_password:
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
				else:
					change_user_password_form._errors['user_password'] = forms.util.ErrorList([u"Passwords don't match"])
					change_user_password_form._errors['confirm_password'] = forms.util.ErrorList([u"Passwords don't match"])
	return render_to_response('custom_modify_user.html', {'targetUser': targetUser, 'targetProfile': targetProfile, 'page_name': page_name, 'modify_user_form': modify_user_form, 'change_user_password_form': change_user_password_form}, context_instance=RequestContext(request))

@admin_required
def custom_add_user_view(request):
	''' The page to add a new user. '''
	page_name = "Admin - Add User"
	if request.method == 'POST':
		add_user_form = AddUserForm(request.POST)
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
			if not verify_username(username):
				add_user_form._errors['username'] = forms.util.ErrorList([u'Invalid username. Must be characters A-Z, a-z, 0-9, or "_"'])
			elif User.objects.filter(username=username).count():
				non_field_error = "This username is taken.  Try one of %s_1 through %s_10." % (username, username)
				add_user_form.errors['__all__'] = add_user_form.error_class([non_field_error])
			elif User.objects.filter(first_name=first_name, last_name=last_name).count():
				non_field_error = "A profile for %s %s already exists with username %s." % (first_name, last_name, User.objects.get(first_name=first_name, last_name=last_name).username)
				add_user_form.errors['__all__'] = add_user_form.error_class([non_field_error])
			elif user_password == confirm_password:
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
			else:
				add_user_form._errors['user_password'] = forms.util.ErrorList([u"Passwords don't match."])
				add_user_form._errors['confirm_password'] = forms.util.ErrorList([u"Passwords don't match."])
	else:
		add_user_form = AddUserForm(initial={'status': UserProfile.RESIDENT})
	return render_to_response('custom_add_user.html', {'page_name': page_name, 'add_user_form': add_user_form}, context_instance=RequestContext(request))

@admin_required
def utilities_view(request):
	''' View for an admin to do maintenance tasks on the site. '''
	return render_to_response('utilities.html', {'page_name': "Admin - Site Utilities"}, context_instance=RequestContext(request))

@admin_required
def anonymous_login_view(request):
	''' View for an admin to log her/himself out and login the anonymous user. '''
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
	messages.add_message(request, messages.INFO, MESSAGES['ANONYMOUS_LOGIN'])
	return HttpResponseRedirect(reverse('homepage'))

@admin_required
def end_anonymous_session_view(request):
	''' End the anonymous session if the user is a superuser. '''
	request.session['ANONYMOUS_SESSION'] = False
	messages.add_message(request, messages.INFO, MESSAGES['ANONYMOUS_SESSION_ENDED'])
	return HttpResponseRedirect(reverse('utilities'))

@admin_required
def recount_view(request):
	''' Recount number_of_messages for all threads and number_of_responses for all requests. '''
	requests_changed = 0
	for req in Request.objects.all():
		recount = Response.objects.filter(request=req).count()
		if req.number_of_responses != recount:
			req.number_of_responses = recount
			req.save()
			requests_changed += 1
	threads_changed = 0
	for thread in Thread.objects.all():
		recount = Message.objects.filter(thread=thread).count()
		if thread.number_of_messages != recount:
			thread.number_of_messages = recount
			thread.save()
			threads_changed += 1
	messages.add_message(request, messages.SUCCESS, MESSAGES['RECOUNTED'].format(requests_changed=requests_changed, request_count=Request.objects.all().count(),
			threads_changed=threads_changed, thread_count=Thread.objects.all().count()))
	return HttpResponseRedirect(reverse('utilities'))

@profile_required
def list_managers_view(request):
	''' Show a list of manager positions with links to view in detail. '''
	managerset = Manager.objects.filter(active=True)
	return render_to_response('list_managers.html', {'page_name': "Managers", 'managerset': managerset}, context_instance=RequestContext(request))

@profile_required
def manager_view(request, managerTitle):
	''' View the details of a manager position.
	Parameters:
		request is an HTTP request
		managerTitle is the URL title of the manager.
	'''
	try:
		targetManager = Manager.objects.get(url_title=managerTitle)
	except Manager.DoesNotExist:
		messages.add_message(request, messages.ERROR, MESSAGES['NO_MANAGER'].format(managerTitle=managerTitle))
		return HttpResponseRedirect(reverse('list_managers'))
	if not targetManager.active:
		messages.add_message(request, messages.ERROR, MESSAGES['INACTIVE_MANAGER'].format(managerTitle=targetManager.title))
	else:
		return render_to_response('view_manager.html', {'page_name': "View Manager", 'targetManager': targetManager}, context_instance=RequestContext(request))

@profile_required
def meta_manager_view(request):
	'''
	A manager of managers.  Display a list of current managers, with links to modify them.
	Also display a link to add a new manager.  Restricted to presidents and superadmins.
	'''
	userProfile = UserProfile.objects.get(user=request.user)
	president = False # whether the user has president privileges
	for pos in Manager.objects.filter(incumbent=userProfile):
		if pos.president:
			president=True
			break
	if (not request.user.is_superuser) and (not president):
		return red_home(request, MESSAGES['PRESIDENT'])
	managerset = Manager.objects.all()
	return render_to_response('meta_manager.html', {'page_name': "Admin - Meta-Manager", 'managerset': managerset}, context_instance=RequestContext(request))

@admin_required
def add_manager_view(request):
	''' View to add a new manager position. Restricted to superadmins and presidents. '''
	userProfile = UserProfile.objects.get(user=request.user)
	president = False # whether the user has president privileges
	for pos in Manager.objects.filter(incumbent=userProfile):
		if pos.president:
			president=True
			break
	if (not request.user.is_superuser) and (not president):
		return red_home(request, MESSAGES['PRESIDENTS_ONLY'])
	if request.method == 'POST':
		form = ManagerForm(request.POST)
		if form.is_valid():
			title = form.cleaned_data['title']
			incumbent = form.cleaned_data['incumbent']
			compensation = form.cleaned_data['compensation']
			duties = form.cleaned_data['duties']
			email = form.cleaned_data['email']
			president = form.cleaned_data['president']
			workshift_manager = form.cleaned_data['workshift_manager']
			active = form.cleaned_data['active']
			url_title = title.lower().replace(' ', '_')
			if Manager.objects.filter(title=title).count():
				form._errors['title'] = forms.util.ErrorList([u"A manager with this title already exists."])
			elif Manager.objects.filter(url_title=url_title).count():
				form._errors['title'] = forms.util.ErrorList([u'This manager title maps to a url that is already taken.  Please note, "Site Admin" and "sITe_adMIN" map to the same URL.'])
			else:
				new_manager = Manager(title=title, url_title=url_title, compensation=compensation, duties=duties, email=email, president=president, workshift_manager=workshift_manager, active=active)
				if incumbent:
					new_manager.incumbent = incumbent
				new_manager.save()
				messages.add_message(request, messages.SUCCESS, MESSAGES['MANAGER_ADDED'].format(managerTitle=title))
				return HttpResponseRedirect(reverse('add_manager'))
	else:
		form = ManagerForm()
	return render_to_response('edit_manager.html', {'page_name': "Admin - Add Manager", 'form': form}, context_instance=RequestContext(request))

@profile_required
def edit_manager_view(request, managerTitle):
	''' View to modify an existing manager. 
	Parameters:
		request is an HTTP request
		managerTitle is URL title of the manager.
	'''
	userProfile = UserProfile.objects.get(user=request.user)
	president = False # whether the user has president privileges
	for pos in Manager.objects.filter(incumbent=userProfile):
		if pos.president:
			president=True
			break
	if (not request.user.is_superuser) and (not president):
		return red_home(request, MESSAGES['PRESIDENTS_ONLY'])
	try:
		targetManager = Manager.objects.get(url_title=managerTitle)
	except Manager.DoesNotExist:
		messages.add_message(request, messages.ERROR, MESSAGES['NO_MANAGER'].format(managerTitle=managerTitle))
		return HttpResponseRedirect(reverse('meta_manager'))
	if request.method == 'POST':
		form = ManagerForm(request.POST)
		if form.is_valid():
			title = form.cleaned_data['title']
			incumbent = form.cleaned_data['incumbent']
			compensation = form.cleaned_data['compensation']
			duties = form.cleaned_data['duties']
			email = form.cleaned_data['email']
			president = form.cleaned_data['president']
			workshift_manager = form.cleaned_data['workshift_manager']
			active = form.cleaned_data['active']
			url_title = title.lower().replace(' ', '_')
			if Manager.objects.filter(title=title).count() and Manager.objects.get(title=title) != targetManager:
				form._errors['title'] = forms.util.ErrorList([u"A manager with this title already exists."])
			elif Manager.objects.filter(url_title=url_title).count() and Manager.objects.get(url_title=url_title) != targetManager:
				form._errors['title'] = forms.util.ErrorList([u'This manager title maps to a url that is already taken.  Please note, "Site Admin" and "sITe_adMIN" map to the same URL.'])
			else:
				targetManager.title = title
				targetManager.url_title = url_title
				if incumbent:
					targetManager.incumbent = incumbent
				targetManager.compensation = compensation
				targetManager.duties = duties
				targetManager.email = email
				targetManager.president = president
				targetManager.workshift_manager = workshift_manager
				targetManager.active = active
				targetManager.save()
				messages.add_message(request, messages.SUCCESS, MESSAGES['MANAGER_SAVED'].format(managerTitle=title))
				return HttpResponseRedirect(reverse('meta_manager'))
		else:
			messages.add_message(request, messages.ERROR, MESSAGES['INVALID_FORM'])
	else:
		form = ManagerForm(initial={'title': targetManager.title, 'incumbent': targetManager.incumbent, 'compensation': targetManager.compensation,
			'duties': targetManager.duties, 'email': targetManager.email, 'president': targetManager.president, 'workshift_manager': targetManager.workshift_manager, 'active': targetManager.active})
	return render_to_response('edit_manager.html', {'page_name': "Admin - Edit Manager", 'form': form, 'manager_title': targetManager.title}, context_instance=RequestContext(request))

@profile_required
def manage_request_types_view(request):
	''' Manage requests.  Display a list of request types with links to edit them.
	Also display a link to add a new request type.  Restricted to presidents and superadmins.
	'''
	userProfile = UserProfile.objects.get(user=request.user)
	president = False # whether the user has president privileges
	for pos in Manager.objects.filter(incumbent=userProfile):
		if pos.president:
			president = True
			break
	if (not request.user.is_superuser) and (not president):
		return red_home(request, MESSAGES['PRESIDENT'])
	request_types = RequestType.objects.all()
	return render_to_response('manage_request_types.html', {'page_name': "Admin - Manage Request Types", 'request_types': request_types},
			context_instance=RequestContext(request))

@profile_required
def add_request_type_view(request):
	''' View to add a new request type.  Restricted to presidents and superadmins. '''
	userProfile = UserProfile.objects.get(user=request.user)
	president = False # whether the user has president privileges
	for pos in Manager.objects.filter(incumbent=userProfile):
		if pos.president:
			president = True
			break
	if (not request.user.is_superuser) and (not president):
		return red_home(request, MESSAGES['PRESIDENT'])
	if request.method == 'POST':
		form = RequestTypeForm(request.POST)
		if form.is_valid():
			name = form.cleaned_data['name']
			relevant_managers = form.cleaned_data['relevant_managers']
			enabled = form.cleaned_data['enabled']
			glyphicon = form.cleaned_data['glyphicon']
			url_name = name.lower().replace(' ', '_')
			if RequestType.objects.filter(name=name).count():
				form._errors['name'] = forms.util.ErrorList([u"A request type with this name already exists."])
			elif RequestType.objects.filter(url_name=url_name).count():
				form._errors['name'] = forms.util.ErrorList([u'This request type name maps to a url that is already taken.  Please note, "Waste Reduction" and "wasTE_RedUCtiON" map to the same URL.'])
			else:
				new_request_type = RequestType(name=name, url_name=url_name, enabled=enabled, glyphicon=glyphicon)
				new_request_type.save()
				for pos in relevant_managers:
					new_request_type.managers.add(pos)
				new_request_type.save()
				messages.add_message(request, messages.SUCCESS, MESSAGES['REQUEST_TYPE_ADDED'].format(typeName=name))
				return HttpResponseRedirect(reverse('manage_request_types'))
		else:
			messages.add_message(request, messages.ERROR, MESSAGES['INVALID_FORM'])
	else:
		form = RequestTypeForm()
	return render_to_response('edit_request_type.html', {'page_name': "Admin - Add Request Type", 'form': form}, context_instance=RequestContext(request))

@profile_required
def edit_request_type_view(request, typeName):
	''' View to edit a new request type.  Restricted to presidents and superadmins.
	Parameters:
		request is an HTTP request
		typeName is the request type's URL name.
	'''
	userProfile = UserProfile.objects.get(user=request.user)
	president = False # whether the user has president privileges
	for pos in Manager.objects.filter(incumbent=userProfile):
		if pos.president:
			president = True
			break
	if (not request.user.is_superuser) and (not president):
		return red_home(request, MESSAGES['PRESIDENT'])
	try:
		requestType = RequestType.objects.get(url_name=typeName)
	except RequestType.DoesNotExist:
		messages.add_message(request, messages.ERROR, MESSAGES['NO_REQUEST_TYPE'].format(typeName=typeName))
		return HttpResponseRedirect(reverse('manage_request_types'))
	if request.method == 'POST':
		form = RequestTypeForm(request.POST)
		if form.is_valid():
			name = form.cleaned_data['name']
			relevant_managers = form.cleaned_data['relevant_managers']
			enabled = form.cleaned_data['enabled']
			glyphicon = form.cleaned_data['glyphicon']
			url_name = name.lower().replace(' ', '_')
			if RequestType.objects.filter(name=name).count() and RequestType.objects.get(name=name) != requestType:
				form._errors['name'] = forms.util.ErrorList([u"A request type with this name already exists."])
			elif RequestType.objects.filter(url_name=url_name).count() and RequestType.objects.get(url_name=url_name) != requestType:
				form._errors['name'] = forms.util.ErrorList([u'This request type name maps to a url that is already taken.  Please note, "Waste Reduction" and "wasTE_RedUCtiON" map to the same URL.'])
			else:
				requestType.name = name
				requestType.url_name = url_name
				requestType.managers = relevant_managers
				requestType.enabled = enabled
				glyphicon = glyphicon
				requestType.save()
				messages.add_message(request, messages.SUCCESS, MESSAGES['REQUEST_TYPE_SAVED'].format(typeName=name))
				return HttpResponseRedirect(reverse('manage_request_types'))
		else:
			messages.add_message(request, messages.ERROR, MESSAGES['INVALID_FORM'])
	else:
		form = RequestTypeForm(initial={'name': requestType.name, 'relevant_managers': requestType.managers.all(), 'enabled': requestType.enabled, 'glyphicon': requestType.glyphicon})
	return render_to_response('edit_request_type.html', {'page_name': "Admin - Edit Request Type", 'form': form, 'requestType': requestType}, context_instance=RequestContext(request))

@profile_required
def requests_view(request, requestType):
	'''
	Generic request view.  Parameters:
		request is the HTTP request
		requestType is URL name of a RequestType.
			e.g. "food", "maintenance", "network", "site" 
	'''
	userProfile = UserProfile.objects.get(user=request.user)
	try:
		request_type = RequestType.objects.get(url_name=requestType)
	except RequestType.DoesNotExist:
		return red_home(request, MESSAGES['NO_REQUEST_TYPE'].format(requestType=requestType))
	page_name = "%s Requests" % request_type.name.title()
	if not request_type.enabled:
		message = "%s requests have been disabled." % request_type.name.title()
		return red_home(request, message)
	relevant_managers = request_type.managers.all()
	manager = False #if the user is a relevant manager
	for position in relevant_managers:
		if position.incumbent == userProfile:
			manager = True
			break
	if manager:
		form = ManagerRequestForm
	else:
		form = RequestForm
	if request.method == 'POST':
		if 'submit_request' in request.POST:
			request_form = form(request.POST)
			if request_form.is_valid():
				body = request_form.cleaned_data['body']
				new_request = Request(owner=userProfile, body=body, request_type=request_type)
				new_request.save()
				return HttpResponseRedirect(reverse('requests', kwargs={'requestType': requestType}))
		elif 'add_response' in request.POST:
			response_form = ResponseForm(request.POST)
			if response_form.is_valid():
				request_pk = response_form.cleaned_data['request_pk']
				body = response_form.cleaned_data['body']
				relevant_request = Request.objects.get(pk=request_pk)
				new_response = Response(owner=userProfile, body=body, request=relevant_request)
				if manager:
					mark_filled = response_form.cleaned_data['mark_filled']
					mark_closed = response_form.cleaned_data['mark_closed']
					relevant_request.closed = mark_closed
					relevant_request.filled = mark_filled
					new_response.manager = True
				relevant_request.change_date = datetime.utcnow().replace(tzinfo=utc)
				relevant_request.save()
				new_response.save()
				return HttpResponseRedirect(reverse('requests', kwargs={'requestType': requestType}))
		elif 'upvote' in request.POST:
			vote_form = VoteForm(request.POST)
			if vote_form.is_valid():
				request_pk = vote_form.cleaned_data['request_pk']
				relevant_request = Request.objects.get(pk=request_pk)
				if userProfile in relevant_request.upvotes.all():
					relevant_request.upvotes.remove(userProfile)
				else:
					relevant_request.upvotes.add(userProfile)
					relevant_request.downvotes.remove(userProfile)
				relevant_request.save()
		elif 'downvote' in request.POST:
			vote_form = VoteForm(request.POST)
			if vote_form.is_valid():
				request_pk = vote_form.cleaned_data['request_pk']
				relevant_request = Request.objects.get(pk=request_pk)
				if userProfile in relevant_request.downvotes.all():
					relevant_request.downvotes.remove(userProfile)
				else:
					relevant_request.downvotes.add(userProfile)
					relevant_request.upvotes.remove(userProfile)
				relevant_request.save()
		else:
			return red_home(request, MESSAGES['UNKNOWN_FORM'])
	request_form = form()
	x = 0 # number of requests loaded
	requests_dict = list() # A pseudo-dictionary, actually a list with items of form (request, [request_responses_list], response_form, upvote, downvote, vote_form)
	for req in Request.objects.filter(request_type=request_type):
		request_responses = Response.objects.filter(request=req)
		if manager:
			form = ResponseForm(initial={'request_pk': req.pk, 'mark_filled': req.filled, 'mark_closed': req.closed})
		else:
			form = ResponseForm(initial={'request_pk': req.pk})
		upvote = userProfile in req.upvotes.all()
		downvote = userProfile in req.downvotes.all()
		vote_form = VoteForm(initial={'request_pk': req.pk})
		requests_dict.append((req, request_responses, form, upvote, downvote, vote_form))
		x += 1
		if x >= max_requests:
			break
	return render_to_response('requests.html', {'manager': manager, 'request_type': request_type.name.title(), 'page_name': page_name, 'request_form': request_form, 'requests_dict': requests_dict}, context_instance=RequestContext(request))

@profile_required
def my_requests_view(request):
	'''
	Show user his/her requests, sorted by request_type.
	'''
	page_name = "My Requests"
	userProfile = UserProfile.objects.get(user=request.user)
	if request.method == 'POST':
		if 'submit_request' in request.POST:
			request_form = RequestForm(request.POST)
			if request_form.is_valid():
				type_pk = request_form.cleaned_data['type_pk']
				body = request_form.cleaned_data['body']
				try:
					request_type = RequestType.objects.get(pk=type_pk)
				except RequestType.DoesNotExist:
					message = "The request type was not recognized.  Please contact an admin for support."
					return red_home(request, message)
				new_request = Request(owner=userProfile, body=body, request_type=request_type)
				new_request.save()
				return HttpResponseRedirect(reverse('my_requests'))
		elif 'add_response' in request.POST:
			response_form = ResponseForm(request.POST)
			if response_form.is_valid():
				request_pk = response_form.cleaned_data['request_pk']
				body = response_form.cleaned_data['body']
				relevant_request = Request.objects.get(pk=request_pk)
				new_response = Response(owner=userProfile, body=body, request=relevant_request)
				for manager_position in relevant_request.request_type.managers.all():
					if manager_position.incumbent == userProfile:
						mark_filled = response_form.cleaned_data['mark_filled']
						mark_closed = response_form.cleaned_data['mark_closed']
						relevant_request.filled = mark_filled
						relevant_request.closed = mark_closed
						relevant_request.change_date = datetime.utcnow().replace(tzinfo=utc)
						relevant_request.save()
						new_response.manager = True
						break
				new_response.save()
		elif 'upvote' in request.POST:
			vote_form = VoteForm(request.POST)
			if vote_form.is_valid():
				request_pk = vote_form.cleaned_data['request_pk']
				relevant_request = Request.objects.get(pk=request_pk)
				if userProfile in relevant_request.upvotes.all():
					relevant_request.upvotes.remove(userProfile)
				else:
					relevant_request.upvotes.add(userProfile)
					relevant_request.downvotes.remove(userProfile)
				relevant_request.save()
		elif 'downvote' in request.POST:
			vote_form = VoteForm(request.POST)
			if vote_form.is_valid():
				request_pk = vote_form.cleaned_data['request_pk']
				relevant_request = Request.objects.get(pk=request_pk)
				if userProfile in relevant_request.downvotes.all():
					relevant_request.downvotes.remove(userProfile)
				else:
					relevant_request.downvotes.add(userProfile)
					relevant_request.upvotes.remove(userProfile)
				relevant_request.save()
		else:
			return red_home(request, MESSAGES['UNKNOWN_FORM'])
	my_requests = Request.objects.filter(owner=userProfile)
	request_dict = list() # A pseudo dictionary, actually a list with items of form (request_type.name.title(), request_form, type_manager, [(request, [list_of_request_responses], response_form, upvote, downvote, vote_form),...])
	for request_type in RequestType.objects.all():
		type_manager = False
		for position in request_type.managers.all():
			if position.incumbent == userProfile:
				type_manager = True
				break
		requests_list = list() # Items are of form (request, [list_of_request_responses], response_form),...])
		type_requests = my_requests.filter(request_type=request_type)
		for req in type_requests:
			responses_list = Response.objects.filter(request=req)
			if type_manager:
				form = ResponseForm(initial={'request_pk': req.pk, 'mark_filled': req.filled, 'mark_closed': req.closed})
			else:
				form = ResponseForm(initial={'request_pk': req.pk})
				form.fields['mark_filled'].widget = forms.HiddenInput()
				form.fields['mark_closed'].widget = forms.HiddenInput()
			upvote = userProfile in req.upvotes.all()
			downvote = userProfile in req.downvotes.all()
			vote_form = VoteForm(initial={'request_pk': req.pk})
			requests_list.append((req, responses_list, form, upvote, downvote, vote_form))
		request_form = RequestForm(initial={'type_pk': request_type.pk})
		request_form.fields['type_pk'].widget = forms.HiddenInput()
		request_dict.append((request_type, request_form, type_manager, requests_list))
	return render_to_response('my_requests.html', {'page_name': page_name, 'request_dict': request_dict}, context_instance=RequestContext(request))

@profile_required
def list_my_requests_view(request):
	'''
	Show user his/her requests in list form.
	'''
	userProfile = UserProfile.objects.get(user=request.user)
	requests = Request.objects.filter(owner=userProfile)
	return render_to_response('list_requests.html', {'page_name': "My Requests", 'requests': requests}, context_instance=RequestContext(request))

@profile_required
def list_user_requests_view(request, targetUsername):
	'''
	Show user his/her requests in list form.
	'''
	if targetUsername == request.user.username:
		return list_my_requests_view(request)
	try:
		targetUser = User.objects.get(username=targetUsername)
		targetProfile = UserProfile.objects.get(user=targetUser)
	except (User.DoesNotExist, UserProfile.DoesNotExist):
		return render_to_response('list_requests.html', {'page_name': "User Not Found"}, context_instance=RequestContext(request))
	page_name = "%s's Requests" % targetUsername
	requests = Request.objects.filter(owner=targetProfile)
	return render_to_response('list_requests.html', {'page_name': page_name, 'requests': requests, 'targetUsername': targetUsername}, context_instance=RequestContext(request))

@profile_required
def all_requests_view(request):
	'''
	Show user a list of enabled request types, the number of requests of each type and a link to see them all.
	'''
	types_dict = list() # Pseudo-dictionary, actually a list with items of form (request_type.name.title(), number_of_type_requests, name, enabled, glyphicon)
	for request_type in RequestType.objects.all():
		number_of_requests = Request.objects.filter(request_type=request_type).count()
		types_dict.append((request_type.name.title(), number_of_requests, request_type.url_name, request_type.enabled, request_type.glyphicon))
	return render_to_response('all_requests.html', {'page_name': "Archives - All Requests", 'types_dict': types_dict}, context_instance=RequestContext(request))

@profile_required
def list_all_requests_view(request, requestType):
	'''
	Show user his/her requests in list form.
	'''
	try:
		request_type = RequestType.objects.get(url_name=requestType)
	except RequestType.DoesNotExist:
		return render_to_response('list_requests.html', {'page_name': "Request Type Not Found"}, context_instance=RequestContext(request))
	requests = Request.objects.filter(request_type=request_type)
	page_name = "Archives - All %s Requests" % request_type.name.title()
	return render_to_response('list_requests.html', {'page_name': page_name, 'requests': requests, 'request_type': request_type}, context_instance=RequestContext(request))

@profile_required
def request_view(request, request_pk):
	'''
	The view of a single request.
	'''
	try:
		relevant_request = Request.objects.get(pk=request_pk)
	except Request.DoesNotExist:
		return render_to_response('view_request.html', {'page_name': "Request Not Found"}, context_instance=RequestContext(request))
	userProfile = UserProfile.objects.get(user=request.user)
	request_responses = Response.objects.filter(request=relevant_request)
	manager = False # Whether the user is a relevant manager for this request
	for position in Manager.objects.filter(incumbent=userProfile):
		if position in relevant_request.request_type.managers.all():
			manager = True
			break
	if request.method == 'POST':
		if 'add_response' in request.POST:
			response_form = ResponseForm(request.POST)
			if response_form.is_valid():
				request_pk = response_form.cleaned_data['request_pk']
				body = response_form.cleaned_data['body']
				new_response = Response(owner=userProfile, body=body, request=relevant_request)
				if manager:
					relevant_request.filled = response_form.cleaned_data['mark_filled']
					relevant_request.closed = response_form.cleaned_data['mark_closed']
					relevant_request.number_of_responses += 1
					relevant_request.change_date = datetime.utcnow().replace(tzinfo=utc)
					relevant_request.save()
					new_response.manager = True
				new_response.save()
		elif 'upvote' in request.POST:
			if userProfile in relevant_request.upvotes.all():
				relevant_request.upvotes.remove(userProfile)
			else:
				relevant_request.upvotes.add(userProfile)
				relevant_request.downvotes.remove(userProfile)
			relevant_request.save()
		elif 'downvote' in request.POST:
			if userProfile in relevant_request.downvotes.all():
				relevant_request.downvotes.remove(userProfile)
			else:
				relevant_request.downvotes.add(userProfile)
				relevant_request.upvotes.remove(userProfile)
			relevant_request.save()
		else:
			return red_home(request, MESSAGES['UNKNOWN_FORM'])
	else:
		response_form = ResponseForm(initial={'mark_filled': relevant_request.filled, 'mark_closed': relevant_request.closed})
		upvote = userProfile in relevant_request.upvotes.all()
		downvote = userProfile in relevant_request.downvotes.all()
		vote_form = VoteForm()
		if not manager:
			response_form.fields['mark_filled'].widget = forms.HiddenInput()
			response_form.fields['mark_closed'].widget = forms.HiddenInput()
	upvote = userProfile in relevant_request.upvotes.all()
	downvote = userProfile in relevant_request.downvotes.all()
	vote_form = VoteForm()
	return render_to_response('view_request.html', {'page_name': "View Request", 'relevant_request': relevant_request, 'request_responses': request_responses, 'upvote': upvote, 'downvote': downvote, 'vote_form': vote_form}, context_instance=RequestContext(request))

@profile_required
def announcements_view(request):
	''' The view of manager announcements. '''
	page_name = "Manager Announcements"
	userProfile = None
	userProfile = UserProfile.objects.get(user=request.user)
	announcement_form = None
	manager_positions = Manager.objects.filter(incumbent=userProfile)
	if manager_positions:
		announcement_form = AnnouncementForm(manager_positions)
	if request.method == 'POST':
		if 'unpin' in request.POST:
			unpin_form = UnpinForm(request.POST)
			if unpin_form.is_valid():
				announcement_pk = unpin_form.cleaned_data['announcement_pk']
				relevant_announcement = Announcement.objects.get(pk=announcement_pk)
				relevant_announcement.pinned = False
				relevant_announcement.save()
				return HttpResponseRedirect(reverse('announcements'))
		elif 'post_announcement' in request.POST:
			announcement_form = AnnouncementForm(manager_positions, post=request.POST)
			if announcement_form.is_valid():
				body = announcement_form.cleaned_data['body']
				manager = announcement_form.cleaned_data['as_manager']
				new_announcement = Announcement(manager=manager, body=body, incumbent=userProfile, pinned=True)
				new_announcement.save()
				return HttpResponseRedirect(reverse('announcements'))
	announcements = Announcement.objects.filter(pinned=True)
	announcements_dict = list() # A pseudo-dictionary, actually a list with items of form (announcement, announcement_unpin_form)
	for a in announcements:
		unpin_form = None
		if (a.manager.incumbent == userProfile) or request.user.is_superuser:
			unpin_form = UnpinForm(initial={'announcement_pk': a.pk})
		announcements_dict.append((a, unpin_form))
	return render_to_response('announcements.html', {'page_name': page_name, 'manager_positions': manager_positions, 'announcements_dict': announcements_dict, 'announcement_form': announcement_form}, context_instance=RequestContext(request))

@profile_required
def all_announcements_view(request):
	''' The view of manager announcements. '''
	page_name = "Archives - All Announcements"
	userProfile = UserProfile.objects.get(user=request.user)
	announcement_form = None
	manager_positions = Manager.objects.filter(incumbent=userProfile)
	if manager_positions:
		announcement_form = AnnouncementForm(manager_positions)
	if request.method == 'POST':
		if 'unpin' in request.POST:
			unpin_form = UnpinForm(request.POST)
			if unpin_form.is_valid():
				announcement_pk = unpin_form.cleaned_data['announcement_pk']
				relevant_announcement = Announcement.objects.get(pk=announcement_pk)
				if relevant_announcement.pinned:
					relevant_announcement.pinned = False
				else:
					relevant_announcement.pinned = True
				relevant_announcement.save()
				return HttpResponseRedirect(reverse('all_announcements'))
		elif ('post_announcement' in request.POST) and manager_positions:
			announcement_form = AnnouncementForm(manager_positions, post=request.POST)
			if announcement_form.is_valid():
				body = announcement_form.cleaned_data['body']
				manager = announcement_form.cleaned_data['as_manager']
				new_announcement = Announcement(manager=manager, body=body, incumbent=userProfile, pinned=True)
				new_announcement.save()
				return HttpResponseRedirect(reverse('all_announcements'))
	announcements = Announcement.objects.all()
	announcements_dict = list() # A pseudo-dictionary, actually a list with items of form (announcement, announcement_pin_form)
	for a in announcements:
		form = None
		if ((a.manager.incumbent == userProfile) or request.user.is_superuser) and not a.pinned:
			form = UnpinForm(initial={'announcement_pk': a.pk})
		elif ((a.manager.incumbent == userProfile) or request.user.is_superuser) and a.pinned:
			form = UnpinForm(initial={'announcement_pk': a.pk})
		announcements_dict.append((a, form))
	return render_to_response('announcements.html', {'page_name': page_name, 'manager_positions': manager_positions, 'announcements_dict': announcements_dict, 'announcement_form': announcement_form}, context_instance=RequestContext(request))
