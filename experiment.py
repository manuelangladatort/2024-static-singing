from markupsafe import Markup
import random
import json
import os
import hashlib
import wave
from urllib.parse import quote

import psynet.experiment
from psynet.asset import ExperimentAsset, Asset, LocalStorage, DebugStorage, FastFunctionAsset, S3Storage  # noqa
from psynet.consent import NoConsent, MainConsent, OpenScienceConsent, AudiovisualConsent
from psynet.modular_page import (
    ModularPage,
    AudioRecordControl,
    AudioPrompt,
    PushButtonControl,
    RadioButtonControl,
)
from psynet.js_synth import JSSynth, Note, HarmonicTimbre, InstrumentTimbre

from psynet.page import InfoPage, SuccessfulEndPage, join
from psynet.timeline import Event, ProgressDisplay, ProgressStage, Timeline, CodeBlock, conditional
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker
from psynet.trial.audio import AudioRecordTrial
from psynet.prescreen import AntiphaseHeadphoneTest
from .goldsmiths_consent import GoldsmithsConsent, GoldsmithsAudioConsent, GoldsmithsOpenScienceConsent

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)


# sing4me
from sing4me import singing_extract as sing
from sing4me import melodies
from .params import singing_2intervals

# experiment
from .instructions import welcome, requirements_mic
from .questionnaire import questionnaire
from .pre_screens import (
    mic_test,
    recording_example,
    singing_performance
)

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)


########################################################################################################################
# Prolific parameters
########################################################################################################################

def get_prolific_settings():
    with open("qualification_prolific_en.json", "r") as f:
        qualification = json.dumps(json.load(f))
    return {
        "recruiter": RECRUITER, 
        "prolific_estimated_completion_minutes": TOTAL_ESTIMATE_TIME_MIN,
        "prolific_recruitment_config": qualification,
        "base_payment": PAYMENT,
        "auto_recruit": True,
        "currency": "£",
        "wage_per_hour": 10,
        "prolific_is_custom_screening": False, # workaround to avoid the default screening question for psynet v11.9
        "prolific_workspace": "Goldsmiths",  
        "prolific_project": "Pilot",  
    }


########################################################################################################################
# Global
########################################################################################################################

DEBUG = False
RECRUITER = "prolific" # "prolific" vs "hotair

TOTAL_ESTIMATE_TIME_MIN = 15
PAYMENT = 2.5

INITIAL_RECRUITMENT_SIZE = 10
NUM_PARTICIPANTS = 70 # decide how many participants we recruit in total
IS_PIANO = False # decide if we use piano timbre or not

TRIALS_PER_PARTICIPANT = 30
TRIALS_PER_PARTICIPANT_PRACTICE = 2

# time estiamtes trials
TIME_ESTIMATE_LISTENING_TRIAL = 5
TIME_ESTIMATE_SINGING_TRIAL = 10 
TIME_ESTIMATE_TRIAL = TIME_ESTIMATE_LISTENING_TRIAL + TIME_ESTIMATE_SINGING_TRIAL


# audio prompt mode
# - "synth": play the melody using Tone.js (`JSSynth`)
# - "wavs": play a pre-rendered `.wav` from trial nodes
AUDIO_PROMPT_MODE = "wavs"  # "synth" | "wavs"
SONIC_LOGOS_STATIC_WAV_DIR = os.path.join("static", "audio", "sonic-logos")
SONIC_LOGOS_STATIC_WAV_URL_PREFIX = "/static/audio/sonic-logos"


def _list_sonic_logo_wavs():
    if not os.path.isdir(SONIC_LOGOS_STATIC_WAV_DIR):
        return []
    wavs = [
        os.path.join(SONIC_LOGOS_STATIC_WAV_DIR, f)
        for f in os.listdir(SONIC_LOGOS_STATIC_WAV_DIR)
        if f.lower().endswith(".wav")
    ]
    wavs.sort()
    return wavs


SONIC_LOGO_WAV_PATHS = _list_sonic_logo_wavs()


def pick_sonic_logo_wav(melody_id: str) -> str | None:
    """
    Deterministically selects a `.wav` file from `SONIC_LOGOS_STATIC_WAV_DIR` based on `melody_id`.
    Returns a local path (or `None` if no wavs are available).
    """
    if not SONIC_LOGO_WAV_PATHS:
        return None
    digest = hashlib.md5(melody_id.encode("utf-8")).hexdigest()
    idx = int(digest[:8], 16) % len(SONIC_LOGO_WAV_PATHS)
    return SONIC_LOGO_WAV_PATHS[idx]


def _wav_duration_seconds(path: str) -> float:
    with wave.open(path, "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
    return frames / float(rate)


def compile_nodes_from_wav_directory(
    wav_dir: str,
    url_prefix: str,
    *,
    limit: int | None = None,
):
    """
    Creates `StaticNode`s directly from a directory of `.wav` files.
    Each node definition contains:
    - `stim_id`: filename without extension
    - `url_audio`: URL served from `static/`
    - `duration_sec`: duration of the wav (for progress timing)
    """
    if not os.path.isdir(wav_dir):
        return []

    wav_files = [f for f in os.listdir(wav_dir) if f.lower().endswith(".wav")]
    wav_files.sort()
    if limit is not None:
        wav_files = wav_files[:limit]

    nodes_out = []
    for filename in wav_files:
        local_path = os.path.join(wav_dir, filename)
        stim_id = os.path.splitext(filename)[0]
        nodes_out.append(
            StaticNode(
                definition={
                    "stim_id": stim_id,
                    "url_audio": f"{url_prefix}/{quote(filename)}",
                    "duration_sec": _wav_duration_seconds(local_path),
                }
            )
        )
    return nodes_out


# singing
roving_width = 2.5
roving_mean = dict(
    default=55,
    low=49,
    high=61
)

NUM_NOTES = 7
NUM_INT = NUM_NOTES - 1
SYLLABLE = "TA"
TIME_AFTER_SINGING = 1.5

REFERENCE_MODE = "pitch_mode"  # pitch_mode vs previous_note vs first_note
MAX_ABS_INT_ERROR_ALLOWED = 5.5  # set to 999 if NUM_INT > 2
MAX_INT_SIZE = 999
MAX_MELODY_PITCH_RANGE = 999  # deactivated
MAX_INTERVAL2REFERENCE = 5
SAVE_PLOT = True # decide if we save the plot of the singing performance or not

# timbre
if IS_PIANO:
    TIMBRE = InstrumentTimbre("piano")
    note_duration_tonejs = 0.5
    note_silence_tonejs = 0.2
else:
    TIMBRE = dict(
        default=HarmonicTimbre(
            attack=0.01,  # Attack phase duration in seconds
            decay=0.05,  # Decay phase duration in seconds
            sustain_amp=0.8,  # Amplitude fraction to decay to relative to max amplitude --> 0.4, 0.7
            release=0.55,  # Release phase duration in seconds
            num_harmonics=10,  # Actual number of partial harmonics to use
            roll_off=14,  # Roll-off in units of dB/octave,
        )
    )
    note_duration_tonejs = 0.8
    note_silence_tonejs = 0

pitch_duration = note_duration_tonejs + note_silence_tonejs


# durations
def estimate_time_per_trial(
        # estimate time for trials: melody and singing duration
        pitch_duration,
        num_pitches,
        time_after_singing
):
    melody_duration = pitch_duration * num_pitches
    singing_duration = melody_duration + time_after_singing
    return melody_duration, singing_duration


melody_duration, singing_duration = estimate_time_per_trial(
    pitch_duration,
    (NUM_NOTES + 1),
    TIME_AFTER_SINGING
)


########################################################################################################################
# Stimuli
########################################################################################################################

def generate_random_melody(mel_id, roving_mean, roving_width, max_interval2reference, num_notes):
    # Function to generate melodies based on a reference_pitch, max_interval2reference, and number of notes (currently not implemented)

    # sample reference pitch
    reference_pitch = melodies.sample_reference_pitch(
        roving_mean,
        roving_width,
    )
    # sample pitches
    target_pitches = melodies.sample_absolute_pitches(
        reference_pitch=reference_pitch,
        max_interval2reference=max_interval2reference,
        num_pitches=num_notes
    )

    # Round each element in the target_pitches list to the nearest integer
    target_pitches = [round(pitch) for pitch in target_pitches]

    # get intervals
    target_intervals = melodies.convert_absolute_pitches_to_interval_sequence(target_pitches, "previous_note")
    # get intervals from pitch to reference pitch
    target_intervals2reference = melodies.convert_absolute_pitches_to_intervals2reference(
        target_pitches, reference_pitch
    )
    return dict(
        melody_id="Melody_" + str(mel_id),
        # reference_pitch=reference_pitch,
        target_pitches=target_pitches,
        target_intervals=target_intervals,
        # target_intervals2reference=target_intervals2reference
    )

# NUM_RAND_MELODIES = 5

# nodes_random = [
#     StaticNode(
#         definition={
#             "melody": generate_random_melody(i, roving_mean["high"], roving_width, MAX_INTERVAL2REFERENCE, NUM_NOTES)
#         },
#     )
#     for i in range(1, (NUM_RAND_MELODIES + 1))
# ]


# We generate trial nodes either from a JSON melody list ("synth") or from a directory of `.wav`s ("wavs").
if AUDIO_PROMPT_MODE == "wavs":
    nodes = compile_nodes_from_wav_directory(
        SONIC_LOGOS_STATIC_WAV_DIR,
        SONIC_LOGOS_STATIC_WAV_URL_PREFIX,
    )
else:
    # we generate the stimulus (and nodes) by importing the melodies from a json file
    path_json = "melodies.json"

    with open(path_json, 'r') as file:
        melodies_data = json.load(file)

    melodies_list = melodies_data['melodies']
        
    nodes = [
        StaticNode(
            definition={
                "melody": {
                    "set_id": melody["set"],
                    "melody_id": melody["melody"],
                    "target_pitches": melody["target_pitches"],
                }
            },
        )
        for melody in melodies_list
    ]


# Practice always stays on synth melodies.
nodes_practice = [
    StaticNode(
        definition={
            "melody": generate_random_melody(i, roving_mean["high"], roving_width, MAX_INTERVAL2REFERENCE, NUM_NOTES)
        },
    )
    for i in range(1, (TRIALS_PER_PARTICIPANT_PRACTICE + 1))
]


########################################################################################################################
# experiment parts
########################################################################################################################

def create_listen_trial(show_current_trial, time_estimate, target_pitches, melody_duration, melody_id: str):
    html = Markup(
        f"""
        <h3>How easy do you think it would be to sing this melody?</h3>
        <br><br>
        {show_current_trial}
        """
    )

    prompt = JSSynth(
        html,
        [Note(pitch) for pitch in target_pitches],
        timbre=TIMBRE,
        default_duration=note_duration_tonejs,
        default_silence=note_silence_tonejs,
    )

    listen_page = ModularPage(
        "listen_page",
        prompt,
        PushButtonControl(
            choices=[1, 2, 3, 4, 5, 6, 7],
            labels=[
                "(1) Very difficult",
                "(2)",
                "(3)",
                "(4)",
                "(5)",
                "(6)",
                "(7) Very easy",
            ],
            arrange_vertically=True,
        ),
        events={
            "responseEnable": Event(is_triggered_by="promptEnd"),
            "submitEnable": Event(is_triggered_by="promptEnd"),
        },
        save_answer="singing_difficulty_rating",
        time_estimate=time_estimate,
    )

    return listen_page


def create_listen_trial_wav(show_current_trial, time_estimate, url_audio: str, prompt_duration: float):
    html = Markup(
        f"""
        <h3>How easy do you think it would be to sing this melody?</h3>
        <br><br>
        {show_current_trial}
        """
    )

    listen_page = ModularPage(
        "listen_page",
        AudioPrompt(url_audio, html),
        PushButtonControl(
            choices=[1, 2, 3, 4, 5, 6, 7],
            labels=[
                "(1) Very difficult",
                "(2)",
                "(3)",
                "(4)",
                "(5)",
                "(6)",
                "(7) Very easy",
            ],
            arrange_vertically=True,
        ),
        events={
            "responseEnable": Event(is_triggered_by="promptEnd"),
            "submitEnable": Event(is_triggered_by="promptEnd"),
        },
        save_answer="singing_difficulty_rating",
        time_estimate=time_estimate,
    )

    return listen_page


def create_singing_trial(show_current_trial, target_pitches, time_estimate, melody_duration, singing_duration, melody_id: str):
    html = Markup(
        f"""
        <h3>Sing back the melody</h3>
        <ul>
          <li>Don’t worry if the melody is too difficult — just try your best.</li>
          <li>Sing each note clearly using the syllable '{SYLLABLE}'.</li>
        </ul>
        <br><br>
        {show_current_trial}<br><br>
        """
    )

    prompt = JSSynth(
        html,
        [Note(pitch) for pitch in target_pitches],
        timbre=TIMBRE,
        default_duration=note_duration_tonejs,
        default_silence=note_silence_tonejs,
    )

    singing_page = ModularPage(
        "singing_page",
        prompt,
        control=AudioRecordControl(
            duration=singing_duration,
            show_meter=True,
            controls=False,
            auto_advance=False,
            bot_response_media="example_audio.wav",
        ),
        events={
            "promptStart": Event(is_triggered_by="trialStart"),
            "recordStart": Event(is_triggered_by="promptEnd", delay=0.25),
        },
        progress_display=ProgressDisplay(
            stages=[
                ProgressStage(melody_duration, "Listen to the melody...", "orange"),
                ProgressStage((singing_duration+1), "Recording...sing back the melody!", "red"),
                ProgressStage(0.5, "Done!", "green", persistent=True),
            ],
        ),
        time_estimate=time_estimate,
    )

    return singing_page


def create_singing_trial_wav(show_current_trial, time_estimate, url_audio: str, prompt_duration: float, singing_duration: float):
    html = Markup(
        f"""
        <h3>Sing back the melody</h3>
        <ul>
          <li>Don’t worry if the melody is too difficult — just try your best.</li>
          <li>Sing each note clearly using the syllable '{SYLLABLE}'.</li>
        </ul>
        <br><br>
        {show_current_trial}<br><br>
        """
    )

    singing_page = ModularPage(
        "singing_page",
        AudioPrompt(url_audio, html),
        control=AudioRecordControl(
            duration=singing_duration,
            show_meter=True,
            controls=False,
            auto_advance=False,
            bot_response_media="example_audio.wav",
        ),
        events={
            "promptStart": Event(is_triggered_by="trialStart"),
            "recordStart": Event(is_triggered_by="promptEnd", delay=0.25),
        },
        progress_display=ProgressDisplay(
            stages=[
                ProgressStage(prompt_duration, "Listen to the melody...", "orange"),
                ProgressStage((singing_duration+1), "Recording...sing back the melody!", "red"),
                ProgressStage(0.5, "Done!", "green", persistent=True),
            ],
        ),
        time_estimate=time_estimate,
    )

    return singing_page


class SingingTrial(AudioRecordTrial, StaticTrial):

    num_pages = 1
    time_estimate = TIME_ESTIMATE_TRIAL
    accumulate_answers = True

    def show_trial(self, experiment, participant):
        is_wav_trial = "url_audio" in self.definition

        if is_wav_trial:
            wav_def = self.definition
        else:
            melody = self.definition

            # convert to right register
            if self.participant.var.register == "high":
                target_pitches = melody['melody']['target_pitches']
            else:
                target_pitches = [(i - 12) for i in melody['melody']['target_pitches']]

        if self.trial_maker_id == "sing_practice":
            total_num_trials = TRIALS_PER_PARTICIPANT_PRACTICE
        else: 
            total_num_trials = TRIALS_PER_PARTICIPANT

        current_trial = self.position + 1
        show_current_trial = f'<i>Trial number {current_trial} out of {total_num_trials} trials.</i>'

        if is_wav_trial:
            prompt_duration = float(wav_def.get("duration_sec", melody_duration))
            wav_singing_duration = prompt_duration + TIME_AFTER_SINGING
            listening_page = create_listen_trial_wav(
                show_current_trial,
                TIME_ESTIMATE_LISTENING_TRIAL,
                wav_def["url_audio"],
                prompt_duration,
            )
            ingo_page = InfoPage(
                Markup(
                    """
                    <h3>Ready to sing?</h3>
                    Click <b><b>Next</b></b> when you are ready to listen to the melody again and sing it back.
                    <br><br>
                    """
                ),
                time_estimate=2,
            )
            singing_page = create_singing_trial_wav(
                show_current_trial,
                TIME_ESTIMATE_SINGING_TRIAL,
                wav_def["url_audio"],
                prompt_duration,
                wav_singing_duration,
            )
        else:
            listening_page = create_listen_trial(
                show_current_trial,
                TIME_ESTIMATE_LISTENING_TRIAL,
                target_pitches,
                melody_duration,
                melody["melody"]["melody_id"],
            )

            singing_page = create_singing_trial(
                show_current_trial,
                target_pitches,
                TIME_ESTIMATE_SINGING_TRIAL,
                melody_duration,
                singing_duration,
                melody["melody"]["melody_id"],
            )
        
        if is_wav_trial:
            return [listening_page, ingo_page, singing_page]
        return [listening_page, singing_page]

    def analyze_recording(self, audio_file: str, output_plot: str):
        is_wav_trial = "url_audio" in self.definition

        if is_wav_trial:
            # For WAV-based prompts we don't have a symbolic pitch target; just extract what was sung.
            raw = sing.analyze(
                audio_file,
                singing_2intervals,
                plot_options=sing.PlotOptions(
                    save=SAVE_PLOT, path=output_plot, format="png"
                ),
            )
            raw = [
                {key: melodies.as_native_type(value) for key, value in x.items()} for x in raw
            ]
            sung_pitches = [x["median_f0"] for x in raw]

            return {
                "failed": False,
                "reason": "NA (wav prompt)",
                "register": getattr(self.participant.var, "register", None),
                "stim_id": self.definition.get("stim_id"),
                "url_audio": self.definition.get("url_audio"),
                "sung_pitches": sung_pitches,
                "num_sung_pitches": len(sung_pitches),
                "raw": raw,
                "save_plot": SAVE_PLOT,
            }

        melody = self.definition

        # convert to right register
        if self.participant.var.register == "high":
            target_pitches =  melody['melody']['target_pitches']
            # reference_pitch =  melody['melody']['reference_pitch']
        else:
            target_pitches = [(i - 12) for i in melody['melody']['target_pitches']]
            # reference_pitch = melody['melody']['reference_pitch'] - 12

        raw = sing.analyze(
            audio_file,
            singing_2intervals,
            target_pitches=target_pitches,
            plot_options=sing.PlotOptions(
                save=SAVE_PLOT, path=output_plot, format="png"
            ),
        )
        raw = [
            {key: melodies.as_native_type(value) for key, value in x.items()} for x in raw
        ]
        sung_pitches = [x["median_f0"] for x in raw]
        sung_intervals = melodies.convert_absolute_pitches_to_interval_sequence(
            sung_pitches,
            "previous_note"
        )
        target_intervals = melodies.convert_absolute_pitches_to_interval_sequence(
            target_pitches,
            "previous_note"
        )
        # sung_intervals2reference = melodies.convert_absolute_pitches_to_intervals2reference(
        #     sung_pitches,
        #     reference_pitch
        # )
        stats = sing.compute_stats(
            sung_pitches,
            target_pitches,
            sung_intervals,
            target_intervals
        )

        # check if failed based on number of sung pitches
        num_sung_pitches = stats["num_sung_pitches"]
        num_target_pitches = stats["num_target_pitches"]
        correct_num_notes = num_sung_pitches == num_target_pitches

        if correct_num_notes:
            failed = False
            reason = "All good"
        else:
            failed = True
            reason = f"Wrong number of sung notes: {num_sung_pitches}  sung out of {num_target_pitches} notes in melody"

        # convert back to high register
        if self.participant.var.register == "low":
            target_pitches = [(i + 12) for i in target_pitches]
            sung_pitches = [(i + 12) for i in sung_pitches]
            # reference_pitch = reference_pitch + 12

        return {
            "failed": failed,
            "reason": reason,
            "register": self.participant.var.register,
            # "reference_pitch": reference_pitch,
            "target_pitches": target_pitches,
            "num_target_pitches": len(target_pitches),
            "target_intervals": target_intervals,
            "sung_pitches": sung_pitches,
            "num_sung_pitches": len(sung_pitches),
            "sung_intervals": sung_intervals,
            # "sung_intervals2reference": sung_intervals2reference,
            "raw": raw,
            "save_plot": SAVE_PLOT,
            "stats": stats,
        }
    
class SingingTrialPractice(SingingTrial):

    def gives_feedback(self, experiment, participant):
        return True

    def show_feedback(self, experiment, participant):
        output_analysis = self.analysis
        num_sung_pitches = len(output_analysis["sung_pitches"])
        num_target_pitches = len(output_analysis["target_pitches"])

        if num_sung_pitches == num_target_pitches:
            return InfoPage(
                Markup(
                    f"""
                    <h3>Your performance is great!</h3>
                    <hr>
                    We detected {num_sung_pitches} notes in your recording.
                    <hr>
                    """
                ),
                time_estimate=2
            )
        elif num_sung_pitches == (num_target_pitches - 1) or num_sung_pitches == (num_target_pitches + 1):
            return InfoPage(
                Markup(
                    f"""
                    <h3>You can do better...</h3>
                    <hr>
                    We detected {num_sung_pitches} notes in your recording, but we asked you to sing {num_target_pitches} notes.
                    <br>
                    Please try to do one or more of the following:
                    <ol><li>Sing each note clearly using the syllable 'TA'.</li>
                        <li>Make sure you computer microphone is working and you are in a quiet environment.</li>
                        <li>Leave a silent gap between the notes.</li>
                        <li>Sing each note for about 1 second.</li>
                    </ol>
                    <b><b>If you don't improve your performance, the experiment will terminate.</b></b>
                    <hr>
                    """
                ),
                time_estimate=2
            )
        else:
            return InfoPage(
                Markup(
                    f"""
                   <h3>Your performance is bad...</h3>
                    <hr>
                    We detected {num_sung_pitches} notes in your recording, but we asked you to sing {num_target_pitches} notes.<br><br>
                    Please try to do one or more of the following:
                    <ol><li>Sing each note clearly using the syllable 'TA'.</li>
                        <li>Make sure you computer microphone is working and you are in a quiet environment.</li>
                        <li>Leave a silent gap between the notes.</li>
                        <li>Sing each note for about 1 second.</li>
                    </ol>
                    <b><b>If you don't improve your performance, the experiment will terminate.</b></b>
                    <hr>
                    """
                ),
                time_estimate=2
            )

class StaticTrialMakerPractice(StaticTrialMaker):
    performance_check_type = "performance"
    performance_threshold = 0
    give_end_feedback_passed = False


practice_singing = join(
    InfoPage("We can now start with the main singing task. But first, we will start with a short practice.", time_estimate=2),
    InfoPage(
        Markup(
            f"""
            <h3>Instructions Practice</h3>
            <hr>
            You will now practice singing to longer melodies consisting of {NUM_NOTES} notes.
            <br><br>
            In each trial, you will first listen to a melody and then sing it back as accurately as possible.
            <br><br>
            We will monitor your responses and give you feedback.
            <hr>
            """
        ),
        time_estimate=3
    ),
    StaticTrialMakerPractice(
        id_="sing_practice",
        trial_class=SingingTrialPractice,
        nodes=nodes_practice,
        expected_trials_per_participant=TRIALS_PER_PARTICIPANT_PRACTICE,
        max_trials_per_participant=TRIALS_PER_PARTICIPANT_PRACTICE,
        recruit_mode="n_participants",
        allow_repeated_nodes=False,
        balance_across_nodes=True,
        check_performance_at_end=True,
        check_performance_every_trial=False,
        target_n_participants=0,
    ),
)


main_singing = join(
    InfoPage("You can now start with the main singing task.", time_estimate=2),
    InfoPage(
        Markup(
            f"""
            <h3>Instructions</h3>
            <hr>
            You will listen to a total of {(TRIALS_PER_PARTICIPANT)} musical melodies. 
            <br><br>
            In each trial, you will first listen to a melody and answer how easy it would be to sing it.
            <br><br>
            You will then listen to the same melody again and sing it back.
            <br><br>
            Do not worry if the melody is difficult to sing. Just try your best to sing the melody as accurately as possible using the syllable 'TA'.
            <hr>
            """
        ),
        time_estimate=3
    ),
    StaticTrialMaker(
        id_="main_singing",
        trial_class=SingingTrial,
        nodes=nodes,
        expected_trials_per_participant=TRIALS_PER_PARTICIPANT,
        max_trials_per_participant=TRIALS_PER_PARTICIPANT,
        recruit_mode="n_participants",
        allow_repeated_nodes=False,
        balance_across_nodes=True,
        target_n_participants=NUM_PARTICIPANTS,
        check_performance_at_end=False,
        check_performance_every_trial=False,
    ),
)


########################################################################################################################
# Timeline
########################################################################################################################

class Exp(psynet.experiment.Experiment):
    label = "Static singing experiment"

    asset_storage = LocalStorage()

    config = {
        **get_prolific_settings(),
        "initial_recruitment_size": INITIAL_RECRUITMENT_SIZE,
        "title": f"Listen to melodies and sing them back! (Headphones required, {TOTAL_ESTIMATE_TIME_MIN} min, £{PAYMENT})",
        "description": Markup("""
            <p>{"You will listen to short melodies and sing them back as accurately as possible (Headphone required, Chrome browser required).".format(
            )}</p>
            <p>{"If you have any questions or concerns, please contact us through Prolific."}</p>
            """),
        "contact_email_on_error": "m.angladatort@gold.ac.uk",
        "organization_name": "Goldsmiths, University of London",
        "show_reward": False
    }

    if DEBUG:
        timeline = Timeline(
            NoConsent(),
            CodeBlock(lambda participant: participant.var.set("register", "low")),  # set singing register to low
            main_singing,
        )

    else:
        timeline = Timeline(
            GoldsmithsConsent(),
            GoldsmithsAudioConsent(),
            GoldsmithsOpenScienceConsent(),

            welcome(),
            requirements_mic(),
            mic_test(),

            singing_performance(),  # here we 1) screen bad participants and 2) select singing register (8 trials)
            conditional( 
                label="assign_register",
                condition=lambda experiment, participant: participant.var.predicted_register == "undefined",
                logic_if_true=CodeBlock(
                    lambda experiment, participant: participant.var.set(
                        "register", random.choice(["low", "high"]))
                ),
                logic_if_false=CodeBlock(lambda experiment, participant: participant.var.set(
                    "register", participant.var.predicted_register)
                                            ),
                fix_time_credit=False
            ),

            # practice_singing, # not implemented 
            main_singing,
            questionnaire(),
        )