
from django.core.validators import RegexValidator, MinValueValidator
from django.db import models

alphanumeric = RegexValidator(r'^[0-9A-Za-z]+$', 'Only alphanumeric characters are allowed.')

class Room(models.Model):
	title = models.CharField(
        unique=True,
        blank=False,
        null=False,
        max_length=100,
        validators=[alphanumeric],
        help_text="The title of the room (i.e. '2E'). Characters A-Z, 0-9.",
        )
	unofficial_name = models.CharField(
        blank=True,
        null=True,
        max_length=100,
        help_text="The unofficial name of the room (i.e. 'Starry Night')",
        )
	description = models.TextField(
        blank=True,
        null=True,
        help_text="The description of this room.",
        )
	occupancy = models.IntegerField(
        default=1,
        validators=[MinValueValidator(0)],
        help_text="The total number of people that this room should house.",
        )

	def __unicode__(self):
		return self.title

	def __str__(self):
		return self.__unicode__()