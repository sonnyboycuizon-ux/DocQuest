from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('requestsystem', '0018_profile_middle_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='student_status',
            field=models.CharField(
                choices=[('student', 'Regular Student'), ('irregular', 'Irregular Student'), ('graduated', 'Graduated')],
                default='student',
                max_length=20,
            ),
        ),
    ]
