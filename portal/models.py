from django.db import models

class Job(models.Model):
    title = models.CharField(max_length=160)
    company = models.CharField(max_length=160)
    location = models.CharField(max_length=160, default='United States')
    employment_type = models.CharField(max_length=60, default='Full-time')
    description = models.TextField()
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f'{self.title} — {self.company}'

class Application(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    full_name = models.CharField(max_length=160)
    email = models.EmailField()
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f'{self.full_name} — {self.job.title}'


class PlatformControl(models.Model):
    """Singleton control for site availability, managed by the owner in Django Admin."""
    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.CharField(
        max_length=240,
        default='Cretan Staffing is temporarily undergoing scheduled maintenance. Please check back soon.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Website availability'
        verbose_name_plural = 'Website availability'

    def __str__(self):
        return 'Website maintenance controls'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
