from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import *

DATE = lambda: forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=60, label='Full name')
    email = forms.EmailField()
    role = forms.ChoiceField(choices=[r for r in ROLES if r[0] != 'admin'])
    phone = forms.CharField(required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'email')

    def save(self, commit=True):
        user = super().save(commit)
        role = self.cleaned_data['role']
        Profile.objects.create(user=user, role=role, phone=self.cleaned_data['phone'])
        if role == 'player':
            Player.objects.create(user=user, name=user.first_name)
        return user


class PlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        exclude = ['user']
        widgets = {'date_of_birth': DATE()}


class PlayerSelfForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = ['name', 'date_of_birth', 'achievements', 'medical_notes']
        widgets = {'date_of_birth': DATE()}


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'city', 'coach']

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields['coach'].queryset = User.objects.filter(profile__role='coach')
        self.fields['coach'].label_from_instance = lambda u: u.get_full_name() or u.username


class VenueForm(forms.ModelForm):
    class Meta:
        model = Venue
        fields = ['name', 'location', 'facilities', 'capacity']


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['venue', 'date', 'slot', 'purpose']
        widgets = {'date': DATE()}


class TournamentForm(forms.ModelForm):
    teams = forms.ModelMultipleChoiceField(queryset=Team.objects.all(), widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Tournament
        fields = ['name', 'sport', 'format', 'start_date']
        widgets = {'start_date': DATE()}

    def clean(self):
        c = super().clean()
        n = len(c.get('teams') or [])
        if 'teams' in c and n < 2:
            raise ValidationError('Select at least two teams.')
        if c.get('format') == 'ko' and n not in (2, 4, 8, 16, 32):
            raise ValidationError('Knockout tournaments need 2, 4, 8, 16 or 32 teams.')
        return c


class ResultForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['date', 'venue', 'score_a', 'score_b']
        widgets = {'date': DATE()}
        labels = {'score_a': 'Score (first team)', 'score_b': 'Score (second team)'}

    def clean(self):
        c = super().clean()
        a, b = c.get('score_a'), c.get('score_b')
        if (a is None) != (b is None):
            raise ValidationError('Enter both scores, or leave both blank.')
        if a is not None and a == b and self.instance.tournament.format == 'ko':
            raise ValidationError('Knockout matches cannot end in a draw.')
        return c


class StatForm(forms.ModelForm):
    class Meta:
        model = PlayerStat
        fields = ['player', 'match', 'points', 'note']


class NotificationForm(forms.ModelForm):
    class Meta:
        model = Notification
        fields = ['title', 'message']
