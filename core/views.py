import csv
import json
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import *
from .models import *
from .perms import PERMS, deny, get_role, need


def L(text, name, *args):
    return {'text': text, 'url': reverse(name, args=args)}


def A(label, name, *args, cls=''):
    return {'label': label, 'url': reverse(name, args=args), 'cls': cls}


def notify(user, title, message):
    Notification.objects.create(title=title, message=message, created_by=user)
    emails = list(User.objects.exclude(email='').values_list('email', flat=True))
    if emails:
        EmailMessage(title, message, bcc=emails).send(fail_silently=True)


def players_qs():
    return Player.objects.select_related('team').annotate(pts=Coalesce(Sum('stats__points'), 0), gp=Count('stats'))


def table(request, title, head, rows, top=(), subtitle='', **extra):
    return render(request, 'table.html', {'title': title, 'head': head, 'rows': rows, 'top_actions': top,
                                          'subtitle': subtitle, **extra})


def simple_form(request, cls, obj, title, back, **kw):
    f = cls(request.POST or None, instance=obj, **kw)
    if request.method == 'POST' and f.is_valid():
        f.save()
        messages.success(request, 'Saved.')
        return redirect(back)
    return render(request, 'form.html', {'form': f, 'title': title, 'back': back})


# ---------- accounts & dashboard ----------
def register(request):
    f = RegisterForm(request.POST or None)
    if request.method == 'POST' and f.is_valid():
        login(request, f.save())
        messages.success(request, 'Welcome! Your account has been created.')
        return redirect('dashboard')
    return render(request, 'registration/register.html', {'form': f})


@login_required
def dashboard(request):
    upcoming = Match.objects.filter(score_a__isnull=True).select_related('team_a', 'team_b', 'venue', 'tournament')
    return render(request, 'dashboard.html', {
        'counts': [('Players', Player.objects.count()), ('Teams', Team.objects.count()),
                   ('Tournaments', Tournament.objects.count()), ('Matches to play', upcoming.count())],
        'upcoming': upcoming[:5], 'top': players_qs().order_by('-pts')[:5],
        'notes': Notification.objects.all()[:3]})


# ---------- players ----------
@login_required
def players(request):
    qs, q, t = players_qs(), request.GET.get('q', '').strip(), request.GET.get('team', '')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(sport__icontains=q))
    if t:
        qs = qs.filter(team_id=t)
    role, med = get_role(request.user), get_role(request.user) in ('admin', 'coach')
    manage = role in PERMS['players']
    rows = []
    for p in qs:
        cells = [L(p.name, 'player', p.pk), p.team or '-', p.sport, p.gp, p.pts] + ([p.medical_notes or 'Fit'] if med else [])
        acts = [A('Edit', 'player_edit', p.pk), A('Delete', 'delete', 'player', p.pk, cls='danger')] if manage else []
        rows.append({'cells': cells, 'actions': acts})
    return table(request, 'Players', ['Name', 'Team', 'Sport', 'Matches', 'Points'] + (['Medical'] if med else []), rows,
                 top=[A('Add player', 'player_add')] if manage else [], search=True, teams=Team.objects.all(), q=q, team=t)


@login_required
def player_detail(request, pk):
    p = get_object_or_404(players_qs(), pk=pk)
    see_med = get_role(request.user) in ('admin', 'coach') or p.user_id == request.user.id
    return render(request, 'player_detail.html', {'p': p, 'see_med': see_med, 'stats': p.stats.select_related('match')[:10],
                                                   'can_edit': get_role(request.user) in PERMS['players'] or p.user_id == request.user.id})


@login_required
def player_form(request, pk=None):
    obj = get_object_or_404(Player, pk=pk) if pk else None
    if get_role(request.user) in PERMS['players']:
        cls = PlayerForm
    elif obj and obj.user_id == request.user.id:
        cls = PlayerSelfForm  # players may edit only their own profile
    else:
        return deny(request)
    return simple_form(request, cls, obj, 'Edit player' if obj else 'Add player', 'players')


# ---------- teams ----------
@login_required
def teams(request):
    manage = get_role(request.user) in PERMS['teams']
    rows = [{'cells': [L(t.name, 'team', t.pk), t.city or '-', (t.coach.get_full_name() or t.coach.username) if t.coach else '-', t.players.count()],
             'actions': [A('Edit', 'team_edit', t.pk), A('Delete', 'delete', 'team', t.pk, cls='danger')] if manage else []}
            for t in Team.objects.select_related('coach')]
    return table(request, 'Teams', ['Team', 'City', 'Coach', 'Players'], rows, top=[A('Create team', 'team_add')] if manage else [])


@login_required
def team_detail(request, pk):
    t = get_object_or_404(Team, pk=pk)
    rows = [{'cells': [L(p.name, 'player', p.pk), p.sport, p.gp, p.pts], 'actions': []} for p in players_qs().filter(team=t)]
    coach = (t.coach.get_full_name() or t.coach.username) if t.coach else 'not assigned'
    return table(request, t.name, ['Player', 'Sport', 'Matches', 'Points'], rows, subtitle=f'Coach: {coach}. Add players by editing a player and choosing this team.')


@need('teams')
def team_form(request, pk=None):
    obj = get_object_or_404(Team, pk=pk) if pk else None
    return simple_form(request, TeamForm, obj, 'Edit team' if obj else 'Create team', 'teams')


# ---------- tournaments & matches ----------
@login_required
def tournaments(request):
    manage = get_role(request.user) in PERMS['tournaments']
    rows = []
    for t in Tournament.objects.all():
        total, done = t.matches.count(), t.matches.filter(score_a__isnull=False).count()
        rows.append({'cells': [L(t.name, 'tournament', t.pk), t.get_format_display().split(' (')[0], t.start_date, f'{done}/{total} played'],
                     'actions': [A('Delete', 'delete', 'tournament', t.pk, cls='danger')] if manage else []})
    return table(request, 'Tournaments', ['Tournament', 'Format', 'Starts', 'Progress'], rows,
                 top=[A('New tournament', 'tournament_add')] if manage else [])


@need('tournaments')
def tournament_add(request):
    f = TournamentForm(request.POST or None)
    if request.method == 'POST' and f.is_valid():
        t = f.save(commit=False)
        t.created_by = request.user
        t.save()
        t.build_fixtures(f.cleaned_data['teams'])
        notify(request.user, f'New tournament: {t.name}', f'{t.name} starts on {t.start_date}. Fixtures are now published.')
        messages.success(request, 'Tournament created and fixtures generated.')
        return redirect('tournament', pk=t.pk)
    return render(request, 'form.html', {'form': f, 'title': 'New tournament', 'back': 'tournaments',
                                         'hint': 'Fixtures are generated automatically from the teams you select.'})


@login_required
def tournament_detail(request, pk):
    t = get_object_or_404(Tournament, pk=pk)
    last = t.matches.aggregate(m=Max('round_no'))['m']
    return render(request, 'tournament_detail.html', {
        't': t, 'matches': t.matches.select_related('team_a', 'team_b', 'venue'), 'standings': t.standings(),
        'can_next': t.format == 'ko' and last and not t.matches.filter(round_no=last, score_a__isnull=True).exists()
                    and t.matches.filter(round_no=last).count() > 1})


@need('tournaments')
@require_POST
def next_round(request, pk):
    t = get_object_or_404(Tournament, pk=pk)
    last = t.matches.aggregate(m=Max('round_no'))['m']
    winners = [m.winner for m in t.matches.filter(round_no=last)]
    if None in winners or len(winners) < 2:
        messages.error(request, 'Record every result in the current round first.')
    else:
        t.add_round([(winners[i], winners[i + 1]) for i in range(0, len(winners), 2)], last + 1)
        messages.success(request, f'Round {last + 1} fixtures generated.')
    return redirect('tournament', pk=pk)


@need('tournaments')
def match_edit(request, pk):
    m = get_object_or_404(Match, pk=pk)
    was = m.played
    f = ResultForm(request.POST or None, instance=m)
    if request.method == 'POST' and f.is_valid():
        m = f.save()
        if m.played and not was:
            notify(request.user, 'Result', f'{m.team_a} {m.score_a} - {m.score_b} {m.team_b} ({m.tournament.name})')
        messages.success(request, 'Match updated.')
        return redirect('tournament', pk=m.tournament_id)
    return render(request, 'form.html', {'form': f, 'title': f'{m.team_a} vs {m.team_b}', 'back': 'tournaments',
                                         'hint': 'Record the result here, or change the date and venue.'})


def _csv(name, header, rows):
    r = HttpResponse(content_type='text/csv')
    r['Content-Disposition'] = f'attachment; filename="{name}"'
    w = csv.writer(r)
    w.writerow(header)
    w.writerows(rows)
    return r


@need('reports')
def standings_csv(request, pk):
    t = get_object_or_404(Tournament, pk=pk)
    return _csv(f'{t.name}-standings.csv', ['Team', 'P', 'W', 'D', 'L', 'For', 'Against', 'Pts'],
                [[s['team'], s['p'], s['w'], s['d'], s['l'], s['gf'], s['ga'], s['pts']] for s in t.standings()])


# ---------- venues & bookings ----------
@login_required
def venues(request):
    manage = get_role(request.user) in PERMS['venues']
    rows = [{'cells': [v.name, v.location or '-', v.facilities or '-', v.capacity],
             'actions': [A('Edit', 'venue_edit', v.pk), A('Delete', 'delete', 'venue', v.pk, cls='danger')] if manage else []}
            for v in Venue.objects.all()]
    return table(request, 'Venues', ['Venue', 'Location', 'Facilities', 'Capacity'], rows,
                 top=[A('Add venue', 'venue_add'), A('Bookings', 'bookings')] if manage else [A('Bookings', 'bookings')])


@need('venues')
def venue_form(request, pk=None):
    obj = get_object_or_404(Venue, pk=pk) if pk else None
    return simple_form(request, VenueForm, obj, 'Edit venue' if obj else 'Add venue', 'venues')


@login_required
def bookings(request):
    manage = get_role(request.user) in PERMS['venues']
    rows = [{'cells': [b.venue, b.date, b.get_slot_display(), b.purpose or '-'],
             'actions': [A('Cancel', 'delete', 'booking', b.pk, cls='danger')] if manage else []}
            for b in Booking.objects.select_related('venue')]
    return table(request, 'Venue bookings', ['Venue', 'Date', 'Slot', 'Purpose'], rows,
                 top=[A('Book a venue', 'booking_add')] if manage else [])


@need('venues')
def booking_add(request):
    f = BookingForm(request.POST or None)
    if request.method == 'POST' and f.is_valid():
        b = f.save(commit=False)
        b.booked_by = request.user
        b.save()
        messages.success(request, 'Venue booked.')
        return redirect('bookings')
    return render(request, 'form.html', {'form': f, 'title': 'Book a venue', 'back': 'bookings'})


# ---------- performance ----------
@login_required
def rankings(request):
    rows = [{'cells': [i, L(p.name, 'player', p.pk), p.team or '-', p.gp, p.pts, f'{p.pts / p.gp:.1f}' if p.gp else '-'], 'actions': []}
            for i, p in enumerate(players_qs().order_by('-pts', 'name'), 1)]
    return table(request, 'Player rankings', ['Rank', 'Player', 'Team', 'Matches', 'Points', 'Average'], rows,
                 top=[A('Record performance', 'stat_add')] if get_role(request.user) in PERMS['stats'] else [])


@need('stats')
def stat_add(request):
    return simple_form(request, StatForm, None, 'Record performance', 'rankings')


# ---------- notifications ----------
@login_required
def notifications(request):
    return render(request, 'notifications.html', {'notes': Notification.objects.select_related('created_by')})


@need('notify')
def notification_add(request):
    f = NotificationForm(request.POST or None)
    if request.method == 'POST' and f.is_valid():
        notify(request.user, f.cleaned_data['title'], f.cleaned_data['message'])
        messages.success(request, 'Announcement sent to all users.')
        return redirect('notifications')
    return render(request, 'form.html', {'form': f, 'title': 'Send announcement', 'back': 'notifications'})


# ---------- reports ----------
@need('reports')
def reports(request):
    top = list(players_qs().order_by('-pts')[:10])
    teams = Team.objects.annotate(pts=Coalesce(Sum('players__stats__points'), 0)).order_by('-pts')
    return render(request, 'reports.html', {
        'players_chart': {'labels': [p.name for p in top], 'data': [p.pts for p in top]},
        'teams_chart': {'labels': [t.name for t in teams], 'data': [t.pts for t in teams]},
        'tournaments': Tournament.objects.all()})


@need('reports')
def players_csv(request):
    return _csv('players.csv', ['Name', 'Team', 'Sport', 'Matches', 'Points'],
                [[p.name, p.team or '', p.sport, p.gp, p.pts] for p in players_qs()])


# ---------- delete ----------
KINDS = {'player': (Player, 'players', 'players'), 'team': (Team, 'teams', 'teams'),
         'tournament': (Tournament, 'tournaments', 'tournaments'), 'venue': (Venue, 'venues', 'venues'),
         'booking': (Booking, 'venues', 'bookings')}


@login_required
def delete(request, kind, pk):
    if kind not in KINDS:
        raise Http404
    model, perm, back = KINDS[kind]
    if get_role(request.user) not in PERMS[perm]:
        return deny(request)
    obj = get_object_or_404(model, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Deleted.')
        return redirect(back)
    return render(request, 'confirm_delete.html', {'obj': obj, 'back': back})
