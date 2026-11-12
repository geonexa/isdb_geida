from django.db import models


class ReferenceDataset(models.Model):
    """
    One seeding event: a dataset from the reference catalogue (REFERENCE_DATA_DIR/catalog.json)
    checked and loaded into the database, or the analysis registry synced from backend/analyses/. The latest row per
    dataset is its current state; earlier rows are the history. Analyses and the admin cite it.
    """

    CATALOGS = [("reference", "Reference data (REFERENCE_DATA_DIR)"), ("registry", "Analysis registry (backend/analyses)")]
    STATUS = [("loaded", "Loaded"), ("recorded", "Already in the database (recorded)"), ("published", "Published"),
              ("checked", "Checked (read at run time)"), ("failed", "Failed")]

    catalog = models.CharField(max_length=10, choices=CATALOGS)
    dataset = models.CharField(max_length=60, db_index=True)
    version = models.CharField(max_length=40, blank=True)
    title = models.CharField(max_length=300)
    status = models.CharField(max_length=10, choices=STATUS)
    folder = models.CharField(max_length=500, help_text="Folder the files were read from")
    files = models.JSONField(default=list, help_text="[{path, bytes, modified}] of the files read")
    fingerprint = models.CharField(max_length=64, blank=True, help_text="SHA-256 over file names, sizes and dates")
    features = models.JSONField(default=dict, help_text="Feature counts from the catalogue")
    rows = models.BigIntegerField(null=True, blank=True, help_text="Rows in the target table after loading")
    table = models.CharField(max_length=100, blank=True)
    source = models.JSONField(default=dict, help_text="Publisher, links, licence, citation from the catalogue")
    report = models.TextField(blank=True)
    loaded_by = models.CharField(max_length=150, blank=True)
    loaded = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-loaded"]
        indexes = [models.Index(fields=["catalog", "dataset", "-loaded"])]
        verbose_name = "reference dataset load"

    def __str__(self):
        return f"{self.dataset} {self.version} ({self.status}, {self.loaded:%Y-%m-%d})"
