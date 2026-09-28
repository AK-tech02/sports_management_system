from datetime import date
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from core.models import *


class Command(BaseCommand):
    help = 'Create demo users, teams, players, venues and a tournament.'

    def handle(self, *a, **k):
        if User.objects.filter(username='admin').exists():
            return self.stdout.write('Demo data already exists.')
        admin = User.objects.create_superuser('admin', 'admin@example.com', 'admin12345', first_name='Site Admin')
        Profile.objects.create(user=admin, role='admin')
        mk = lambda n, r, name: (lambda u: (Profile.objects.create(user=u, role=r), u)[1])(
            User.objects.create_user(n, f'{n}@example.com', 'demo12345', first_name=name))
        org, coach = mk('organizer', 'organizer', 'Olivia Organizer'), mk('coach', 'coach', 'Rahul Kulkarni')
        coach2 = mk('coach2', 'coach', 'Sunita Deshmukh')
        teams = [Team.objects.create(name=n, city=c, coach=co) for n, c, co in [
            ('Mumbai Strikers', 'Mumbai', coach), ('Pune Panthers', 'Pune', coach2),
            ('Nashik Knights', 'Nashik', None), ('Thane Titans', 'Thane', None)]]
        names = ['Aarav Mehta', 'Diya Nair', 'Rohan Iyer', 'Sana Khan', 'Kabir Shah', 'Isha Patil', 'Vikram Rao', 'Meera Joshi']
        players = [Player.objects.create(name=n, team=teams[i // 2], achievements='College level champion' if i % 2 else 'State MVP',
                                         medical_notes='Recovering from knee strain' if i == 2 else '') for i, n in enumerate(names)]
        pu = mk('player', 'player', 'Aarav Mehta')
        players[0].user = pu
        players[0].save()
        for name, loc, fac, cap in [('Central Ground', 'Mumbai', 'Floodlights, pavilion', 5000),
                                    ('Riverside Stadium', 'Pune', 'Turf pitch, gym, medical room', 3000),
                                    ('Campus Arena', 'Thane', 'Indoor nets', 800)]:
            Venue.objects.create(name=name, location=loc, facilities=fac, capacity=cap)
        t = Tournament.objects.create(name='Inter-College Cup', format='rr', start_date=date.today(), created_by=org)
        t.build_fixtures(teams)
        for m, (a, b) in zip(t.matches.all()[:3], [(180, 150), (200, 200), (120, 175)]):
            m.score_a, m.score_b = a, b
            m.save()
            for p in Player.objects.filter(team__in=[m.team_a, m.team_b]):
                PlayerStat.objects.create(player=p, match=m, points=20 + (p.id * 17) % 60)
        Notification.objects.create(title='Welcome', message='Registrations for the Inter-College Cup are open.', created_by=org)
        self.stdout.write(self.style.SUCCESS('Demo data created. Logins: admin/admin12345, organizer|coach|player / demo12345'))
