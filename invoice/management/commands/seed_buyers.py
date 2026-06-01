"""
Management command to seed all buyers from the old 더푸드 system.
Run with: python manage.py seed_buyers
"""
from django.core.management.base import BaseCommand
from invoice.models import Buyer

BUYERS = [
    '에이스호프',
    '나베식품',
    '해송상회',
    '청호동',
    '고은식품',
    '정진푸드',
    '영화',
    '남양',
    '이례',
    '정우상회',
    '이어',
    '해광',
    '청해',
    '세종',
    '금어',
    '해륙',
    '싸다건어물',
    '영동',
    '극동',
    '광산',
    '형제',
    '함미희',
    '명가',
    '소현',
    '동성물산',
    '늘푸른',
    '믿음',
    '레이젠',
    '창원nc',
    '해양수산',
    '한양건해',
    '풍익상회',
    '대서양건해',
    '청해식품',
    '동아유통',
    '경주상회',
    '우리홈마트',
    '세진식품',
    '보경',
    '본사광주까투리',
    '맛있는 술안주',
    '태성상회',
    '조성현',
    '유나상회',
]


class Command(BaseCommand):
    help = 'Seed all buyers from the old 더푸드 Excel system'

    def handle(self, *args, **kwargs):
        created = 0
        skipped = 0

        for name in BUYERS:
            buyer, was_created = Buyer.objects.get_or_create(name=name)
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'  Created: {name}'))
            else:
                skipped += 1
                self.stdout.write(self.style.WARNING(f'  Skipped (exists): {name}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done — {created} created, {skipped} already existed.'
        ))
