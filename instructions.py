from markupsafe import Markup
from psynet.page import InfoPage


def welcome():
    return InfoPage(
        Markup(
            """
            <h3>Welcome</h3>
            <hr>
            In this experiment, you will hear melodies and asked to sing them back as accurately as possible.
            <br><br>
            Press <b><b>next</b></b> when you are ready to start.
            <hr>
            """
        ),
        time_estimate=3
    )


def requirements_mic():
    return InfoPage(
        Markup(
            """
            <h3>Technical requirements</h3>
            <hr>
            <b><b>You will need to use a working microphone, either from your headphones or computer</b></b>. 
            <br><br>
            If you are not able to satisfy these requirements currently, please return the study now and come back later.
            <hr>
            """
        ),
        time_estimate=3
    )
