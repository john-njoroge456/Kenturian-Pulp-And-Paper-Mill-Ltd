from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.urls import reverse
import uuid


User = get_user_model()


class OrderRequest(models.Model):
    """A client-submitted request to order paper rolls. Not a checkout/payment
    flow — this feeds Sales, who follow up with a quote/confirmation."""

    # Adjust these to match your actual product line names.

    UNIT_CHOICES = [
        ("rolls", "Rolls"),
        ("kg", "Kilograms"),
        ("tons", "Tons"),
    ]

    STATUS_CHOICES = [
        ("new", "New"),
        ("reviewed", "Reviewed"),
        ("quoted", "Quoted"),
        ("confirmed", "Confirmed"),
        ("closed", "Closed"),
    ]

    reference = models.CharField(
        max_length=20, unique=True, editable=False, blank=True)

    # Order parameters
    item_description = models.CharField(max_length=200)
    color = models.CharField(max_length=100, blank=True,
                             help_text="Leave blank if natural/unspecified")
    length = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Length in millimetres")
    gsm = models.PositiveIntegerField(
        help_text="Paper weight, grams per square metre")
    quantity = models.PositiveIntegerField(
        help_text="Quantity in kilograms (kg)")
    # Client / logistics
    company_name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=150)
    phone = models.CharField(max_length=30)
    email = models.EmailField()
    delivery_location = models.CharField(max_length=200, blank=True)
    preferred_delivery_date = models.DateField(null=True, blank=True)

    # Attachments / notes
    lpo_file = models.FileField(
        upload_to="order_lpos/%Y/%m/", blank=True, null=True)
    notes = models.TextField(blank=True)

    # Internal tracking
    # Internal tracking
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default="new")
    client_email_sent = models.BooleanField(
        default=False, help_text="Whether the confirmation copy reached the client's email")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"KPM-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} — {self.company_name}"


class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    theme_color = models.CharField(
        max_length=7,
        default="#14335c",
        help_text="Hex color for this product's slide background, e.g. #8b5e3c for brown paper"
    )
    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Lower numbers show first in the homepage slideshow"
    )
    # make owner optional so seed data can create products without an explicit user
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='products', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', '-created_at']

    def __str__(self):
        return self.name


class NewsCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True, blank=True)

    class Meta:
        verbose_name_plural = "News categories"
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class NewsTag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class NewsArticle(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    excerpt = models.TextField(blank=True)
    body = models.TextField()
    featured_image = models.ImageField(
        upload_to='news/', blank=True, null=True)
    category = models.ForeignKey(
        NewsCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='articles')
    tags = models.ManyToManyField(NewsTag, blank=True, related_name='articles')
    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='news_articles')
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-published_at', '-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            n = 1
            while NewsArticle.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f"{base_slug}-{n}"
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('main:news_detail', kwargs={'slug': self.slug})

    def __str__(self):
        return self.title


class GalleryImage(models.Model):
    CATEGORY_CHOICES = [
        ('home_hero', 'Homepage Hero Carousel'),
        ('about_hero', 'About Page Banner'),
        ('about_story', 'About Page — Our Story'),
        ('careers_hero', 'Careers Page Banner'),
        ('order_hero', 'Order Page Banner'),
        ('news_hero', 'News Page Banner'),
        ('contact_hero', 'Contact Page Banner'),
        ('general', 'General / Uncategorized'),

    ]

    title = models.CharField(max_length=255)
    image = models.ImageField(upload_to='gallery/')
    caption = models.TextField(blank=True)
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default='general')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', '-uploaded_at']

    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"


class JobPosting(models.Model):
    QUALIFICATION_CHOICES = [
        ('none', 'No formal qualification required'),
        ('certificate', 'Certificate'),
        ('diploma', 'Diploma'),
        ('bachelors', "Bachelor's Degree"),
        ('masters', "Master's Degree"),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=255)
    department = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=100, blank=True)
    employment_type = models.CharField(
        max_length=50, blank=True)  # e.g. "Full-time", "Contract"
    qualification = models.CharField(
        max_length=20, choices=QUALIFICATION_CHOICES, blank=True)
    description = models.TextField()
    is_open = models.BooleanField(default=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


def validate_quote_length(value):
    word_count = len(value.split())
    if word_count > 70:
        raise ValidationError(
            f'Quote is {word_count} words — please shorten it to 70 words or fewer '
            'so it displays fully on the careers page.'
        )


class EmployeeStory(models.Model):
    author_name = models.CharField(max_length=150)
    author_role = models.CharField(max_length=150, blank=True)
    quote = models.TextField(
        validators=[validate_quote_length],
        help_text="Keep to 70 words or fewer — longer quotes will be rejected."
    )
    photo = models.ImageField(upload_to='stories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(
        default=0, help_text="Lower numbers show first")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"{self.author_name} — {self.author_role}"


class LeadershipMember(models.Model):
    name = models.CharField(max_length=100)
    # e.g. "Chairman and Managing Director"
    title = models.CharField(max_length=100)
    bio = models.TextField(max_length=500, blank=True)
    photo = models.ImageField(upload_to='leadership/')
    order = models.PositiveIntegerField(
        default=0, help_text="Lower numbers appear first")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.name} ({self.title})"


class OrderItemOption(models.Model):
    """Selectable items on the Place an Order form — managed separately
    from Product, which drives the homepage carousel."""
    name = models.CharField(max_length=200, unique=True)
    is_active = models.BooleanField(
        default=True, help_text="Uncheck to hide from the order form without deleting")
    display_order = models.PositiveIntegerField(
        default=0, help_text="Lower numbers show first")

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = "Order item option"

    def __str__(self):
        return self.name


class ContactMessage(models.Model):
    reference = models.CharField(
        max_length=20, unique=True, editable=False, blank=True)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=255)
    message = models.TextField()
    client_email_sent = models.BooleanField(
        default=False, help_text="Whether the confirmation copy reached the sender's email")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"CTC-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} — {self.name}"


class JobApplication(models.Model):
    reference = models.CharField(
        max_length=20, unique=True, editable=False, blank=True)
    job = models.ForeignKey(
        JobPosting, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='applications', help_text="Blank for speculative applications")
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    message = models.TextField()
    cv_file = models.FileField(upload_to="applications/%Y/%m/")
    client_email_sent = models.BooleanField(
        default=False, help_text="Whether the confirmation copy reached the applicant's email")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"APP-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} — {self.name}"
