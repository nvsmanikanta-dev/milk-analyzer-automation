from decimal import Decimal
from django.test import TestCase

from analyzer.models import QCEntry
from analyzer.services.analyzer_reader import calculate_clr, parse_text


class ParserTests(TestCase):
    def test_labeled_fat_snf(self):
        self.assertEqual(parse_text("FAT: 4.50 SNF: 8.60"), (4.5, 8.6))

    def test_simple_two_number_fallback(self):
        self.assertEqual(parse_text("4.25 8.45"), (4.25, 8.45))

    def test_clr_formula(self):
        self.assertEqual(calculate_clr(4.5, 8.6), 29.18)


class DuplicateSampleTests(TestCase):
    def test_unique_date_shift_sample(self):
        QCEntry.objects.create(
            date="2026-08-21",
            shift="PM",
            sample_code=1,
            fat=Decimal("4.50"),
            snf=Decimal("8.60"),
            clr=Decimal("29.18"),
        )
        self.assertEqual(QCEntry.objects.count(), 1)


from analyzer.services.sync_service import sync_local_to_server


class ServerSyncTests(TestCase):
    databases = {"default", "server"}

    def setUp(self):
        QCEntry.objects.using("default").create(
            date="2026-08-21",
            shift="PM",
            sample_code=11,
            fat=Decimal("4.50"),
            snf=Decimal("8.60"),
            clr=Decimal("29.18"),
            analyzer_code="Analyzer01",
        )

    def test_sync_pushes_server_and_removes_local(self):
        result = sync_local_to_server("2026-08-21", "PM")

        self.assertTrue(result["ok"])
        self.assertEqual(result["pushed"], 1)
        self.assertEqual(QCEntry.objects.using("default").count(), 0)
        self.assertEqual(QCEntry.objects.using("server").count(), 1)

    def test_server_values_match_local_values(self):
        sync_local_to_server("2026-08-21", "PM")
        server_row = QCEntry.objects.using("server").get(sample_code=11)

        self.assertEqual(server_row.fat, Decimal("4.50"))
        self.assertEqual(server_row.snf, Decimal("8.60"))
        self.assertEqual(server_row.clr, Decimal("29.18"))
