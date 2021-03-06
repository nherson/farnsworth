'''
Project: Farnsworth

Author: Karandeep Singh Nagra
'''

from django import template
from django.core.urlresolvers import reverse

register = template.Library()

@register.simple_tag
def wurl(url_name, *args, **kwargs):
    args = [i for i in args if i]
    kwargs = dict((i, j) for i, j in kwargs.items() if j)
    return reverse(url_name, args=args, kwargs=kwargs)
