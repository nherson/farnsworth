'''
Project: Farnsworth

Author: Karandeep Singh Nagra
'''

from django import forms
from farnsworth.settings import house, time_formats

def EventForm(manager_positions, initial=None, post=None):
	class InnerEventForm(forms.Form):
		title = forms.CharField(max_length=100, widget=forms.TextInput())
		description = forms.CharField(widget=forms.Textarea())
		location = forms.CharField(max_length=100, widget=forms.TextInput())
		rsvp = forms.BooleanField(required=False, label="RSVP")
		start_time = forms.DateTimeField(widget=forms.DateTimeInput,
						 input_formats=time_formats)
		end_time = forms.DateTimeField(widget=forms.DateTimeInput,
					       input_formats=time_formats)
		as_manager = forms.ModelChoiceField(queryset=manager_positions, required=False,
						    label="As manager (if manager event)")

		def is_valid(self):
			if not super(InnerEventForm, self).is_valid():
				return False
			start_time = self.cleaned_data['start_time']
			end_time = self.cleaned_data['end_time']
			if start_time > end_time:
				self.errors['__all__'] = self.error_class(["Start time is later than end time. Unless this event involves time travel, please change the start or end time."])
				return False
			return True

	if post is None:
		if initial is None:
			return InnerEventForm(initial={'rsvp': True, 'location': house})
		else:
			return InnerEventForm(initial=initial)
	else:
		return InnerEventForm(post)
