from django.db import models


# Create your models here.
class Plot(models.Model):
    session_id = models.CharField(max_length=128, primary_key=True)
    data = models.TextField(default='')
    weapon_performance_per_hit = models.BinaryField(null=True)
    weapon_performance_totals = models.BinaryField(null=True)
    mean_delivered = models.BinaryField()
    top_delivered = models.BinaryField()
    incoming_per_hit = models.BinaryField(null=True)
    incoming_totals = models.BinaryField(null=True)
    mean_received = models.BinaryField()
    top_received = models.BinaryField()
    total_received = models.BinaryField()
