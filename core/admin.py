from django.contrib import admin
from .models import *

for m in (Profile, Team, Player, Venue, Booking, Tournament, Match, PlayerStat, Notification):
    admin.site.register(m)
