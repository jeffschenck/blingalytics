from django.db import models


class AllTheData(models.Model):
    """Star-schema-style Model for testing purposes."""
    user_id = models.IntegerField()
    user_is_active = models.BooleanField()
    widget_id = models.IntegerField()
    widget_price = models.DecimalField(max_digits=10, decimal_places=2)
