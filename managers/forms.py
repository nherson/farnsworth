'''
Project: Farnsworth

Author: Karandeep Singh Nagra
'''
from django import forms
from django.contrib.auth.models import Group
from django.core.validators import validate_email

from threads.models import UserProfile

class ProfileRequestForm(forms.Form):
	''' Form to create a new profile request. '''
	username = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'50'}), help_text='Characters A-Z, a-z, 0-9, or "_".')
	first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'50'}))
	last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'50'}))
	email = forms.EmailField(max_length=100)
	affiliation_with_the_house = forms.ChoiceField(choices=UserProfile.STATUS_CHOICES)

class AddUserForm(forms.Form):
	''' Form to add a new user and associated profile. '''
	username = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'50'}), help_text='Characters A-Z, a-z, 0-9, or "_".')
	first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'50'}))
	last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'50'}))
	email = forms.EmailField(max_length=100, required=False)
	email_visible_to_others = forms.BooleanField(required=False)
	phone_number = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'size':'50'}))
	phone_visible_to_others = forms.BooleanField(required=False)
	status = forms.ChoiceField(choices=UserProfile.STATUS_CHOICES)
	current_room = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'size':'50'}), required=False)
	former_rooms = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'50'}), required=False)
	former_houses = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size': '50'}), required=False)
	is_active = forms.BooleanField(required=False)
	is_staff = forms.BooleanField(required=False)
	is_superuser = forms.BooleanField(required=False)
	groups = forms.ModelMultipleChoiceField(queryset=Group.objects.all(), required=False)
	user_password = forms.CharField(max_length=100, widget=forms.PasswordInput(attrs={'size':'50'}))
	confirm_password = forms.CharField(max_length=100, widget=forms.PasswordInput(attrs={'size':'50'}))

class ModifyUserForm(forms.Form):
	''' Form to modify an existing user and profile. '''
	first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'50'}))
	last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'50'}))
	email = forms.EmailField(max_length=100, required=False)
	email_visible_to_others = forms.BooleanField(required=False)
	phone_number = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'size':'50'}))
	phone_visible_to_others = forms.BooleanField(required=False)
	status = forms.ChoiceField(choices=UserProfile.STATUS_CHOICES)
	current_room = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'size':'50'}), required=False)
	former_rooms = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'50'}), required=False)
	former_houses = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'50'}), required=False)
	is_active = forms.BooleanField(required=False, help_text="Whether this user can login.")
	is_staff = forms.BooleanField(required=False, help_text="Whether this user can access the Django admin interface.")
	is_superuser = forms.BooleanField(required=False, help_text="Whether this user has admin privileges.")
	groups = forms.ModelMultipleChoiceField(queryset=Group.objects.all(), required=False)

class ChangeUserPasswordForm(forms.Form):
	''' Form for an admin to change a user's password. '''
	user_password = forms.CharField(max_length=100, widget=forms.PasswordInput(attrs={'size':'50'}))
	confirm_password = forms.CharField(max_length=100, widget=forms.PasswordInput(attrs={'size':'50'}))

class ModifyProfileRequestForm(forms.Form):
	''' Form to modify a profile request. '''
	username = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'50'}), help_text='Characters A-Z, a-z, 0-9, or "_".')
	first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'50'}))
	last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'50'}))
	email = forms.EmailField(max_length=100, required=False)
	email_visible_to_others = forms.BooleanField(required=False)
	phone_number = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'size':'50'}))
	phone_visible_to_others = forms.BooleanField(required=False)
	status = forms.ChoiceField(choices=UserProfile.STATUS_CHOICES)
	current_room = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'size':'50'}), required=False)
	former_rooms = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size':'50'}), required=False)
	former_houses = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'size': '50'}), required=False)
	is_active = forms.BooleanField(required=False, help_text="Whether this user can login.")
	is_staff = forms.BooleanField(required=False, help_text="Whether this user can access the Django admin interface.")
	is_superuser = forms.BooleanField(required=False, help_text="Whether this user has admin privileges.")
	groups = forms.ModelMultipleChoiceField(queryset=Group.objects.all(), required=False)
	user_password = forms.CharField(max_length=100, widget=forms.PasswordInput(attrs={'size':'50'}))
	confirm_password = forms.CharField(max_length=100, widget=forms.PasswordInput(attrs={'size':'50'}))

class RequestForm(forms.Form):
	''' Form to create a new Request. '''
	type_pk = forms.IntegerField(required=False)
	body = forms.CharField(widget=forms.Textarea())

class ResponseForm(forms.Form):
	'''' Form for a regular user to create a new Response. '''
	request_pk = forms.IntegerField(widget=forms.HiddenInput())
	body = forms.CharField(widget=forms.Textarea())

class ManagerResponseForm(RequestForm):
	''' Form for a manager to create a new Response. '''
	request_pk = forms.IntegerField(widget=forms.HiddenInput(), required=False)
	body = forms.CharField(widget=forms.Textarea())
	mark_filled = forms.BooleanField(required=False)
	mark_closed = forms.BooleanField(required=False)

def AnnouncementForm(manager_positions, post=None):
	''' Return a form to post an announcement, has an as_manager field if the user is a manager.
	Parameters:
		manager_positions should be a choice set containing manager positions the user making the request currently holds.
		post should be a boolean indicating if the user has any manager positions.
	'''
	class InnerAnnouncementForm(forms.Form):
		as_manager = forms.ModelChoiceField(queryset=manager_positions)
		body = forms.CharField(widget=forms.Textarea())
	if post is None:
		return InnerAnnouncementForm(initial={'as_manager': manager_positions[0].pk})
	else:
		return InnerAnnouncementForm(post)
