from django.db import models
from django.conf import settings

class Faculty(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='faculty',
        primary_key=True
    )
    faculty_id = models.CharField(max_length=20, unique=True, db_index=True)
    department = models.CharField(max_length=100)
    position = models.CharField(max_length=100)
    research_areas = models.TextField(blank=True)

    class Meta:
        db_table = 'accounts_faculty'
        verbose_name = 'Faculty Profile'
        verbose_name_plural = 'Faculty Profiles'
        indexes = [
            models.Index(fields=['department']),
        ]
    @property
    def id(self):
        """Return the user_id as the faculty id"""
        return self.user_id
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.faculty_id}"