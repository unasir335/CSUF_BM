from django.db import models
from django.conf import settings

class Student(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student',
        primary_key=True
    )
    student_id = models.CharField(max_length=20, unique=True, db_index=True)
    major = models.CharField(max_length=100)
    year = models.IntegerField()

    class Meta:
        db_table = 'accounts_student'
        verbose_name = 'Student Profile'
        verbose_name_plural = 'Student Profiles'
        indexes = [
            models.Index(fields=['major', 'year']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.student_id}"