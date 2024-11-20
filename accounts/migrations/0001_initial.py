# Generated by Django 5.1.1 on 2024-10-31 16:22

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Account',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('first_name', models.CharField(max_length=50)),
                ('last_name', models.CharField(max_length=50)),
                ('username', models.CharField(db_index=True, max_length=50, unique=True)),
                ('email', models.EmailField(db_index=True, max_length=100, unique=True)),
                ('phone_number', models.CharField(blank=True, max_length=17, validators=[django.core.validators.RegexValidator(message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.", regex='^\\+?1?\\d{9,15}$')])),
                ('profile_picture', models.ImageField(blank=True, default='users/profile_pics/80x80.png', null=True, upload_to='profile_pics/')),
                ('security_question', models.CharField(blank=True, default='', max_length=255)),
                ('security_answer', models.CharField(blank=True, default='', max_length=255)),
                ('is_admin', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('is_staff', models.BooleanField(default=False)),
                ('is_student', models.BooleanField(default=False)),
                ('is_faculty', models.BooleanField(default=False)),
                ('registration_complete', models.BooleanField(default=False)),
                ('assigned_by_superuser', models.BooleanField(default=False)),
                ('date_joined', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('last_login', models.DateTimeField(auto_now=True)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'account',
                'verbose_name_plural': 'accounts',
            },
        ),
        migrations.CreateModel(
            name='Address',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('address_line1', models.CharField(blank=True, max_length=100)),
                ('address_line2', models.CharField(blank=True, max_length=100)),
                ('city', models.CharField(blank=True, max_length=50)),
                ('state', models.CharField(blank=True, max_length=50)),
                ('country', models.CharField(blank=True, max_length=50)),
                ('zipcode', models.CharField(blank=True, max_length=10)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='address', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='OrderHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_number', models.CharField(max_length=20)),
                ('order_date', models.DateTimeField(auto_now_add=True)),
                ('total_amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='order_history', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-order_date'],
            },
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(blank=True, max_length=50)),
                ('last_name', models.CharField(blank=True, max_length=50)),
                ('phone_number', models.CharField(blank=True, max_length=17, null=True, validators=[django.core.validators.RegexValidator(message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.", regex='^\\+?1?\\d{9,15}$')])),
                ('profile_picture', models.ImageField(blank=True, default='/profile_pics/300x150.png', upload_to='users/profile_pictures')),
                ('address_line1', models.CharField(blank=True, max_length=100)),
                ('address_line2', models.CharField(blank=True, max_length=100)),
                ('city', models.CharField(blank=True, max_length=50)),
                ('state', models.CharField(blank=True, max_length=50)),
                ('country', models.CharField(blank=True, max_length=50)),
                ('zipcode', models.CharField(blank=True, max_length=10)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='userprofile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Faculty',
            fields=[
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='faculty', serialize=False, to=settings.AUTH_USER_MODEL)),
                ('faculty_id', models.CharField(db_index=True, max_length=20, unique=True)),
                ('department', models.CharField(max_length=100)),
                ('position', models.CharField(max_length=100)),
                ('research_areas', models.TextField(blank=True)),
            ],
            options={
                'verbose_name': 'Faculty Profile',
                'verbose_name_plural': 'Faculty Profiles',
                'db_table': 'accounts_faculty',
                'indexes': [models.Index(fields=['department'], name='accounts_fa_departm_048557_idx')],
            },
        ),
        migrations.CreateModel(
            name='Student',
            fields=[
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='student', serialize=False, to=settings.AUTH_USER_MODEL)),
                ('student_id', models.CharField(db_index=True, max_length=20, unique=True)),
                ('major', models.CharField(max_length=100)),
                ('year', models.IntegerField()),
            ],
            options={
                'verbose_name': 'Student Profile',
                'verbose_name_plural': 'Student Profiles',
                'db_table': 'accounts_student',
                'indexes': [models.Index(fields=['major', 'year'], name='accounts_st_major_ae0eb7_idx')],
            },
        ),
        migrations.AddIndex(
            model_name='account',
            index=models.Index(fields=['email', 'username'], name='accounts_ac_email_d9a9b8_idx'),
        ),
        migrations.AddIndex(
            model_name='account',
            index=models.Index(fields=['is_active', 'is_staff'], name='accounts_ac_is_acti_fba305_idx'),
        ),
    ]
