from django.dispatch import Signal

story_published = Signal()
story_unpublished = Signal()
story_hidden = Signal()
story_unhidden = Signal()
