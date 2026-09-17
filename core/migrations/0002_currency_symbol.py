from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="currency",
            name="symbol",
            field=models.CharField(
                default="", max_length=10, unique=True, verbose_name="Symbol"
            ),
            preserve_default=False,
        ),
    ]
