from django.dispatch import Signal

# Sent when a story request reaches READY_FOR_USER so that the stories app can react.
story_ready = Signal()

