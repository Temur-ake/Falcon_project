# Generated by Django 5.0.6 on 2024-07-24 12:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apps', '0003_alter_review_rating'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='users/image/'),
        ),
    ]