from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class QCEntry(models.Model):
    SHIFT_CHOICES = [("AM", "AM"), ("PM", "PM")]

    date = models.DateField()
    shift = models.CharField(max_length=2, choices=SHIFT_CHOICES)
    sample_code = models.PositiveIntegerField()

    fat = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(15)],
    )
    snf = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(20)],
    )
    clr = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
    )

    analyzer_code = models.CharField(max_length=30, default="Analyzer01")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["date", "shift", "sample_code"],
                name="unique_qc_sample_per_date_shift",
            )
        ]

    def __str__(self):
        return f"{self.date} {self.shift} - Sample {self.sample_code}"
