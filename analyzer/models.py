from django.db import models


# Create your models here.
class Plot(models.Model):
    session_id = models.CharField(max_length=128, primary_key=True)
    data = models.TextField(default='')
    mean_delivered = models.BinaryField()
    top_delivered = models.BinaryField()
    mean_received = models.BinaryField()
    top_received = models.BinaryField()
    total_received = models.BinaryField()
