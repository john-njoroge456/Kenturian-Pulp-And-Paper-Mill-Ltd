from django.core.management.base import BaseCommand
from django.utils import timezone

from main.models import Product, NewsArticle, GalleryImage

class Command(BaseCommand):
    help = 'Seed the database with sample products, news, and gallery images'

    def handle(self, *args, **options):
        if Product.objects.exists() or NewsArticle.objects.exists() or GalleryImage.objects.exists():
            self.stdout.write(self.style.WARNING('Data already exists; skipping seeding.'))
            return

        # Create sample products
        p1 = Product.objects.create(
            name='Recycled Kraft Paper',
            description='High-strength recycled kraft paper suitable for packaging and industrial applications.',
            price=12.50,
        )
        p2 = Product.objects.create(
            name='Newsprint Recycled',
            description='Affordable newsprint made from recycled fibers, ideal for printing and publishing.',
            price=5.00,
        )

        # Create sample news
        NewsArticle.objects.create(
            title='Kenturian opens new recycling line',
            excerpt='We are excited to announce a new recycling production line.',
            body='Our new line increases recycling capacity and improves quality. This is part of our sustainability efforts to reduce waste and increase circularity.',
            published_at=timezone.now(),
        )

        # Gallery placeholders — we reference placeholder images from placehold.co
        GalleryImage.objects.create(
            title='Factory Exterior',
            image='gallery/factory1.jpg'
        )
        GalleryImage.objects.create(
            title='Paper Rolls',
            image='gallery/paperrolls.jpg'
        )
        GalleryImage.objects.create(
            title='Recycling Process',
            image='gallery/process.jpg'
        )

        self.stdout.write(self.style.SUCCESS('Sample data created.'))
