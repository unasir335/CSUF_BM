# Generated by Django 5.1.1 on 2024-11-16 16:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_userprofile_profile_picture_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='account',
            name='profile_picture',
            field=models.ImageField(blank=True, default='static/profile_pics/200x200.png', null=True, upload_to='profile_pics/'),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='profile_picture',
            field=models.ImageField(blank=True, default='profile_pictures/200x200.png', upload_to='users/profile_pictures/'),
        ),
    ]
