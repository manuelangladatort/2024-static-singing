import os
from typing import Optional
from psynet.timeline import CodeBlock
from psynet.timeline import Module, Page, conditional, get_template, join
from psynet.page import RejectedConsentPage
from psynet.consent import Consent


#############
# Goldsmiths
#############
def get_template(name):
    assert isinstance(name, str)
    path_template = os.path.join("templates", name) 
    with open(path_template, "r") as file:
        return file.read()


class GoldsmithsConsent(Module):
    """
    Goldsmiths University Consent Form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 30,
    ):
        label = "goldsmiths_consent"
        elts = join(
            self.GoldsmithsConsentPage(),
            conditional(
                "goldsmiths_consent_conditional",
                lambda experiment, participant: (
                    not participant.answer["goldsmiths_consent"]
                ),
                RejectedConsentPage(),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "goldsmiths_consent", participant.answer["goldsmiths_consent"]
                )
            ),
        )
        super().__init__(label, elts)

    class GoldsmithsConsentPage(Page, Consent):
        """
        This page displays the Goldsmiths University consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        def __init__(
            self,
            time_estimate: Optional[float] = 30,
        ):
            super().__init__(
                time_estimate=time_estimate,
                template_str=get_template("goldsmiths_consent.html"),
            )

        def format_answer(self, raw_answer, **kwargs):
            return {"goldsmiths_consent": raw_answer}

        def get_bot_response(self, experiment, bot):
            return {"goldsmiths_consent": True}


###############
# Audiovisual #
###############
class GoldsmithsAudioConsent(Module):
    """
    The Goldsmiths audio consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 30,
    ):
        label = "goldsmiths_audio_consent"
        elts = join(
            self.GoldsmihtsAudioConsentPage(),
            conditional(
                "audiovisual_consent_conditional",
                lambda experiment, participant: (
                    not participant.answer["goldsmiths_audio_consent"]
                ),
                RejectedConsentPage(failure_tags=["goldsmiths_audio_consent_rejected"]),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "goldsmiths_audio_consent", participant.answer["goldsmiths_audio_consent"]
                )
            ),
        )
        super().__init__(label, elts)

    class GoldsmihtsAudioConsentPage(Page, Consent):
        """
        This page displays the Goldsmiths audio consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        def __init__(
            self,
            time_estimate: Optional[float] = 30,
        ):
            super().__init__(
                time_estimate=time_estimate,
                template_str=get_template("goldsmiths_audio_consent.html"),
            )

        def format_answer(self, raw_answer, **kwargs):
            return {"goldsmiths_audio_consent": raw_answer}

        def get_bot_response(self, experiment, bot):
            return {"goldsmiths_audio_consent": True}


################
# Open science #
################
class GoldsmithsOpenScienceConsent(Module):
    """
    The Goldsmiths open science consent form.

    Parameters
    ----------

    time_estimate:
        Time estimated for the page.
    """

    def __init__(
        self,
        time_estimate: Optional[float] = 30,
    ):
        label = "goldsmihts_open_science_consent"
        elts = join(
            self.GoldsmihtsOpenScienceConsentPage(),
            conditional(
                "goldsmihts_open_science_consent_conditional",
                lambda experiment, participant: (
                    not participant.answer["goldsmihts_open_science_consent"]
                ),
                RejectedConsentPage(failure_tags=["goldsmihts_open_science_consent_rejected"]),
            ),
            CodeBlock(
                lambda participant: participant.var.set(
                    "goldsmihts_open_science_consent", participant.answer["goldsmihts_open_science_consent"]
                )
            ),
        )
        super().__init__(label, elts)

    class GoldsmihtsOpenScienceConsentPage(Page, Consent):
        """
        This page displays the Goldsmiths open science consent page.

        Parameters
        ----------

        time_estimate:
            Time estimated for the page.
        """

        def __init__(
            self,
            time_estimate: Optional[float] = 30,
        ):
            super().__init__(
                time_estimate=time_estimate,
                template_str=get_template("goldsmiths_open_science_consent.html"),
            )

        def format_answer(self, raw_answer, **kwargs):
            return {"goldsmihts_open_science_consent": raw_answer}

        def get_bot_response(self, experiment, bot):
            return {"goldsmihts_open_science_consent": True}
