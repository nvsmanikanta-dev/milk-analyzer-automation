from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="QCEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("shift", models.CharField(choices=[("AM", "AM"), ("PM", "PM")], max_length=2)),
                ("sample_code", models.PositiveIntegerField()),
                ("fat", models.DecimalField(decimal_places=2, max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(15)])),
                ("snf", models.DecimalField(decimal_places=2, max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(20)])),
                ("clr", models.DecimalField(decimal_places=2, max_digits=6, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(50)])),
                ("analyzer_code", models.CharField(default="Analyzer01", max_length=30)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-id"]},
        ),
        migrations.AddConstraint(
            model_name="qcentry",
            constraint=models.UniqueConstraint(
                fields=("date", "shift", "sample_code"),
                name="unique_qc_sample_per_date_shift",
            ),
        ),
    ]
