'''
Project: Farnsworth

Author: Karandeep Singh Nagra
'''

from django.shortcuts import render_to_response, render
from django.http import HttpResponseRedirect
from django import forms
from django.core.urlresolvers import reverse
from django.template import RequestContext
from farnsworth.settings import house, ADMINS
from django.contrib.auth import logout, login, authenticate
from models import UserProfile, Thread, Message
from django.utils import timezone
from django.forms.formsets import formset_factory
import datetime

def red_ext(request, function_locals):
	'''
	Convenience function for redirecting users who don't have site access to the external page.
	Parameters:
		request - the request in the calling function
		function_locals - the output of locals() in the calling function
	'''
	return render_to_response('external.html', function_locals, context_instance=RequestContext(request))

def red_home(request, function_locals):
	'''
	Convenience function for redirecting users who don't have access to a page to the home page.
	Parameters:
		request - the request in the calling function
		function_locals - the output of locals() in the calling function
	'''
	return render_to_response('homepage.html', function_locals, context_instance=RequestContext(request))

def homepage_view(request):
	''' The view of the homepage. '''
	homepage = True
	pagename = "Home Page"
	house_name = house
	admin = ADMINS[0]
	if request.user.is_authenticated():
		user = request.user
		staff = user.is_staff
		return red_home(request, locals())
	else:
		user = None
		staff = False
		return red_ext(request, locals())

def external_view(request):
	''' The external landing. '''
	homepage = True
	pagename = "Home Page"
	admin = ADMINS[0]
	house_name = house
	if request.user.is_authenticated():
		user = request.user
		staff = user.is_staff
	else:
		user = None
		staff = False
	return red_ext(request, locals())

def help_view(request):
	''' The view of the helppage. '''
	pagename = "Help Page"
	house_name = house
	admin = ADMINS[0]
	if request.user.is_authenticated():
		user = request.user
		staff = user.is_staff
	else:
		user = None
		staff = False
	return render_to_response('helppage.html', locals(), context_instance=RequestContext(request))

def site_map_view(request):
	''' The view of the site map. '''
	pagename = "Site Map"
	house_name = house
	admin = ADMINS[0]
	if request.user.is_authenticated():
		user = request.user
		staff = user.is_staff
	else:
		user = None
		staff = False
	return render_to_response('site_map.html', locals(), context_instance=RequestContext(request))

def profile_view(request):
	''' The view of the profile page. '''
	pagename = "Profile Page"
	house_name = house
	admin = ADMINS[0]
	if request.user.is_authenticated():
		user = request.user
		staff = user.is_staff
		userProfile = UserProfile.objects.get(user=user)
		if not userProfile:
			message = "A profile for you could not be found.  Please contact an admin for support."
			return red_ext(request, locals())
	else:
		user = None
		staff = False
	class ResetPasswordForm(forms.Form):
		current_password = forms.Charfield(max_length=100, widget=forms.TextInput(attrs={'size':'100'}))
		new_password = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'100'}))
		confirm_password = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'100'}))
	

def login_view(request):
	''' The view of the login page. '''
	pagename = "Login Page"
	house_name = house
	admin = ADMINS[0]
	if request.user.is_authenticated():
		return HttpResponseRedirect(reverse('homepage'))
	user = None
	staff = False
	class loginForm(forms.Form):
		username = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'50'}))
		password = forms.CharField(max_length=100, widget=forms.PasswordInput(attrs={'size':'50'}))
	if request.method == 'POST':
		form = loginForm(request.POST)
		if form.is_valid():
			username = form.cleaned_data['username']
			password = form.cleaned_data['password']
			user = authenticate(username=username, password=password)
			if user is not None:
				if user.is_active:
					login(request, user)
					return HttpResponseRedirect(reverse('homepage'))
				else:
					non_field_error = "Your account is not active.  Please contact the site administrator to activate your account."
			else:
				non_field_error = "Invalid username/password combo"
	else:
		form = loginForm()
	return render(request, 'login.html', locals())

def logout_view(request):
	''' Log the user out. '''
	logout(request)
	return HttpResponseRedirect(reverse('homepage'))

def member_forums_view(request):
	''' Forums for current members. '''
	pagename = "Member Forums"
	house_name = house
	admin = ADMINS[0]
	userProfile = None
	if request.user.is_authenticated():
		user = request.user
		staff = user.is_staff
		#profile = UserProfile.objects.get(user=user)
		for profile in UserProfile.objects.all():
			if profile.user == user:
				userProfile = profile
				break
		if not userProfile:
			pagename = "Home Page"
			homepage = True
			message = "A profile for you could not be found.  Please contact an admin for support."
			return red_ext(request, locals())
	else:
		user = None
		staff = False
		return red_ext(request, locals())
	class ThreadForm(forms.Form):
		subject = forms.CharField(max_length=300, widget=forms.TextInput(attrs={'size':'100'}))
		body = forms.CharField(widget=forms.Textarea(attrs={'class':'thread'}))
	class MessageForm(forms.Form):
		thread_pk = forms.IntegerField()
		#body = forms.CharField(widget=forms.Textarea(attrs={'class':'message'}))
	if request.method == 'POST':
		if 'submit_thread_form' in request.POST:
			thread_form = ThreadForm(request.POST)
			if thread_form.is_valid():
				subject = thread_form.cleaned_data['subject']
				body = thread_form.cleaned_data['body']
				thread = Thread(owner=userProfile, subject=subject, number_of_messages=0, active=True)
				thread.number_of_messages = 1
				thread.save()
				message = Message(body=body, owner=userProfile, thread=thread)
				message.save()
			else:
				print thread_form.errors
		elif 'submit_message_form' in request.POST:
			message_form = MessageForm(request.POST)
			if message_form.is_valid():
				thread_pk = message_form.cleaned_data['thread_pk']
				body = message_form.cleaned_data['body']
				thread = Thread.objects.get(pk=thread_pk)
				message = Message(body=body, owner=userProfile, thread=thread)
				message.save()
				thread.number_of_messages += 1
				thread.save()
			else:
				print message_form.errors
		else:
			pagename = "Home page"
			homepage = True
			return red_home(request, locals())
	week_ago = timezone.now() - datetime.timedelta(days=7)
	active_messages = list()
	my_messages = list()
	for message in Message.objects.all():
		if week_ago < message.post_date:
			active_messages.append(message)
		if message.owner.user == user:
			my_messages.append(message)
	active_threads = list()
	my_threads = list()
	for message in active_messages:
		if message.thread not in active_threads:
			active_threads.append(message.thread)
	for message in my_messages:
		if message.thread not in my_threads:
			my_threads.append(message.thread)
	active_message_forms = list()
	my_message_forms = list()
	for thread in active_threads:
		form = MessageForm(initial={'thread_pk': thread.pk})
		form.fields['thread_pk'].widget = forms.HiddenInput()
		active_message_forms.append(form)
	for thread in my_threads:
		form = MessageForm(initial={'thread_pk': thread.pk})
		form.fields['thread_pk'].widget = forms.HiddenInput()
		my_message_forms.append(form)
	thread_form = ThreadForm()
	return render_to_response('member_forums.html', locals(), context_instance=RequestContext(request))
