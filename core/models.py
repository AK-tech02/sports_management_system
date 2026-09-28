import random
from datetime import timedelta
from django.contrib.auth.models import User
from django.db import models

ROLES = [('admin', 'Administrator'), ('organizer', 'Organizer'), ('coach', 'Coach'), ('player', 'Player')]
SLOTS = [('morning', 'Morning (8-12)'), ('afternoon', 'Afternoon (12-4)'), ('evening', 'Evening (4-8)')]


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLES, default='player')
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f'{self.user.username} ({self.role})'


class Team(models.Model):
    name = models.CharField(max_length=80, unique=True)
    coach = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='teams')
    city = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Player(models.Model):
    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='player')
    name = models.CharField(max_length=100)
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL, related_name='players')
    sport = models.CharField(max_length=50, default='Cricket')
    date_of_birth = models.DateField(null=True, blank=True)
    achievements = models.TextField(blank=True)
    medical_notes = models.TextField(blank=True, help_text='Visible to admins, coaches and this player only.')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Venue(models.Model):
    name = models.CharField(max_length=80, unique=True)
    location = models.CharField(max_length=120, blank=True)
    facilities = models.CharField(max_length=200, blank=True)
    capacity = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name


class Booking(models.Model):
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='bookings')
    date = models.DateField()
    slot = models.CharField(max_length=10, choices=SLOTS)
    purpose = models.CharField(max_length=120, blank=True)
    booked_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['date', 'slot']
        constraints = [models.UniqueConstraint(
            fields=['venue', 'date', 'slot'], name='no_double_booking',
            violation_error_message='This venue is already booked for that date and slot.')]

    def __str__(self):
        return f'{self.venue} {self.date} {self.slot}'


def round_robin(teams):
    """Circle method: every team plays every other team once, one round per matchday."""
    t = list(teams)
    if len(t) % 2:
        t.append(None)
    n, rounds = len(t), []
    for _ in range(n - 1):
        rounds.append([(t[i], t[n - 1 - i]) for i in range(n // 2) if t[i] and t[n - 1 - i]])
        t = [t[0], t[-1]] + t[1:-1]
    return rounds


class Tournament(models.Model):
    FORMATS = [('rr', 'Round robin (everyone plays everyone)'), ('ko', 'Knockout')]
    name = models.CharField(max_length=100)
    sport = models.CharField(max_length=50, default='Cricket')
    format = models.CharField(max_length=2, choices=FORMATS, default='rr')
    start_date = models.DateField()
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def add_round(self, pairs, round_no):
        venues = list(Venue.objects.all())
        day = self.start_date + timedelta(days=7 * (round_no - 1))
        for i, (a, b) in enumerate(pairs):
            Match.objects.create(tournament=self, team_a=a, team_b=b, round_no=round_no, date=day,
                                 venue=venues[i % len(venues)] if venues else None)

    def build_fixtures(self, teams):
        teams = list(teams)
        if self.format == 'rr':
            for n, pairs in enumerate(round_robin(teams), 1):
                self.add_round(pairs, n)
        else:
            random.shuffle(teams)
            self.add_round([(teams[i], teams[i + 1]) for i in range(0, len(teams), 2)], 1)

    def standings(self):
        rows = {}
        row = lambda t: rows.setdefault(t.id, {'team': t, 'p': 0, 'w': 0, 'd': 0, 'l': 0, 'gf': 0, 'ga': 0, 'pts': 0})
        for m in self.matches.select_related('team_a', 'team_b'):
            a, b = row(m.team_a), row(m.team_b)
            if not m.played:
                continue
            a['p'] += 1; b['p'] += 1
            a['gf'] += m.score_a; a['ga'] += m.score_b
            b['gf'] += m.score_b; b['ga'] += m.score_a
            if m.score_a > m.score_b:
                a['w'] += 1; b['l'] += 1; a['pts'] += 3
            elif m.score_a < m.score_b:
                b['w'] += 1; a['l'] += 1; b['pts'] += 3
            else:
                a['d'] += 1; b['d'] += 1; a['pts'] += 1; b['pts'] += 1
        return sorted(rows.values(), key=lambda r: (-r['pts'], -(r['gf'] - r['ga']), r['team'].name))


class Match(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='matches')
    team_a = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='+')
    team_b = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='+')
    venue = models.ForeignKey(Venue, null=True, blank=True, on_delete=models.SET_NULL)
    date = models.DateField()
    round_no = models.PositiveSmallIntegerField(default=1)
    score_a = models.PositiveIntegerField(null=True, blank=True)
    score_b = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['round_no', 'date', 'id']

    def __str__(self):
        return f'{self.team_a} vs {self.team_b}'

    @property
    def played(self):
        return self.score_a is not None and self.score_b is not None

    @property
    def winner(self):
        if not self.played or self.score_a == self.score_b:
            return None
        return self.team_a if self.score_a > self.score_b else self.team_b


class PlayerStat(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='stats')
    match = models.ForeignKey(Match, null=True, blank=True, on_delete=models.SET_NULL)
    points = models.PositiveIntegerField(help_text='Runs, goals or points scored.')
    note = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Notification(models.Model):
    title = models.CharField(max_length=120)
    message = models.TextField()
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
