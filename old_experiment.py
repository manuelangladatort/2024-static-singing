from markupsafe import Markup
import random
import json

import psynet.experiment
from psynet.asset import ExperimentAsset, Asset, LocalStorage, DebugStorage, FastFunctionAsset, S3Storage  # noqa
from psynet.consent import NoConsent, MainConsent, OpenScienceConsent, AudiovisualConsent
from psynet.modular_page import ModularPage, AudioRecordControl
from psynet.js_synth import JSSynth, Note, HarmonicTimbre, InstrumentTimbre

from psynet.page import InfoPage, SuccessfulEndPage, join
from psynet.timeline import Event, ProgressDisplay, ProgressStage, Timeline, CodeBlock, conditional
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker
from psynet.trial.audio import AudioRecordTrial
from psynet.prescreen import AntiphaseHeadphoneTest

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
        # "id": "singing-nets",
        "prolific_estimated_completion_minutes": 11,
        "prolific_maximum_allowed_minutes": 30,
        "prolific_recruitment_config": qualification,
        "base_payment": 2.0,
        "auto_recruit": False,
        "currency": "£",
        "wage_per_hour": 0.0
    }


########################################################################################################################
# Global
########################################################################################################################

# TODO: block randomization of melodies per set
# TODO: repeat each singing trial 2 times


DEBUG = False
RECRUITER = "prolific" # "prolific" vs "hotair

INITIAL_RECRUIT_SIZE = 5
IS_PIANO = False # decide if we use piano timbre or not
INITIAL_RECRUITMENT_SIZE = 5 # decide how many participants we recruit initially
NUM_PARTICIPANTS = 50 # decide how many participants we recruit in total

# time estiamtes trials
TIME_ESTIMATE_LISTENING_TRIAL = 7
TIME_ESTIMATE_SINGING_TRIAL = 15 
TIME_ESTIMATE_TRIAL = TIME_ESTIMATE_LISTENING_TRIAL + TIME_ESTIMATE_SINGING_TRIAL



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


# we generate the stimulus (and nodes) by importing the melodies from a json file
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

NUM_MELODIES = len(nodes)
TRIALS_PER_PARTICIPANT = NUM_MELODIES
TRIALS_PER_PARTICIPANT_PRACTICE = 2

# generate random melodies for the practice phase
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

def create_listen_trial(show_current_trial, time_estimate, target_pitches, melody_duration):
    listen_page = ModularPage(
        "listen_page",
        JSSynth(
            Markup(
                f"""
                <h3>Listen to the melody</h3>
                <hr>
                Press <b><b>Next</b></b> when you are ready to start singing the melody.<br>
                <hr>
                {show_current_trial}<br><br>
                """
                ),
            [Note(pitch) for pitch in target_pitches],
            timbre=TIMBRE,
            default_duration=note_duration_tonejs,
            default_silence=note_silence_tonejs,
            ),
            events={
                "promptStart": Event(is_triggered_by="trialStart", delay=1.5),
                "responseEnable": Event(is_triggered_by="promptEnd", delay=1),
                "submitEnable": Event(is_triggered_by="promptEnd", delay=1),
                },
            progress_display=ProgressDisplay(
                stages=[
                    ProgressStage(1, "Wait a moment...", "orange"),
                    ProgressStage(melody_duration, "Listen to the melody", "red"),
                    ProgressStage(0.5, "Done!", "green", persistent=True),
                    ],
                    ),
            time_estimate=time_estimate,
            )

    return listen_page


def create_singing_trial(show_current_trial, target_pitches, time_estimate, melody_duration, singing_duration):
    singing_page = ModularPage(
        "singing_page",
            JSSynth(
                Markup(
                    f"""
                <h3>Sing back the melody</h3>
                <hr>
                Sing each note clearly using the syllable '{SYLLABLE}' and leave silent gaps between notes.<br><br>
                <hr>
                {show_current_trial}<br><br>
                """
                ),
                [Note(pitch) for pitch in target_pitches],
                timbre=TIMBRE,
                default_duration=note_duration_tonejs,
                default_silence=note_silence_tonejs,
            ),
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
                    ProgressStage(singing_duration, "Recording...SING THE MELODY!", "red"),
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

        
        listening_page = create_listen_trial(
            show_current_trial,
            TIME_ESTIMATE_LISTENING_TRIAL,
            target_pitches,
            melody_duration
        )

        singing_page = create_singing_trial(
            show_current_trial,
            target_pitches,
            TIME_ESTIMATE_SINGING_TRIAL,
            melody_duration,
            singing_duration
            )
        
        return [listening_page, singing_page]

    def analyze_recording(self, audio_file: str, output_plot: str):

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
    InfoPage("We can now start with the main singing task. Please pay attention to the instructions.", time_estimate=2),
    InfoPage(
        Markup(
            f"""
            <h3>Instructions</h3>
            <hr>
            You will listen to a total of {(TRIALS_PER_PARTICIPANT)} musical melodies. 
            <br><br>
            In each trial, you will first listen to a melody and then sing it back as accurately as possible.
            <br><br>
            Please sing each note clearly to the syllable 'TA' and leave silent gaps between notes.
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
        "title": "Singing experiment (Chrome browser, ~11 mins)",
        "description": "This is a singing experiment. You will listen to melodies and sing them back as accurately as possible.",
        "contact_email_on_error": "computational.audition+online_running_manu@gmail.com",
        "organization_name": "Max Planck Institute for Empirical Aesthetics",
        "show_reward": False
    }

    if DEBUG:
        timeline = Timeline(
            NoConsent(),
            CodeBlock(lambda participant: participant.var.set("register", "low")),  # set singing register to low
            welcome(),
            practice_singing,
            main_singing,
            SuccessfulEndPage()
        )

    else:
        timeline = Timeline(
            MainConsent(),
            AudiovisualConsent(),
            OpenScienceConsent(),
            welcome(),
            requirements_mic(),
            mic_test(),
            # recording_example(),
            singing_performance(),  # here we 1) screen bad participants and 2) select singing register (8 trials)
            conditional(
                label="assign_register",
                condition=lambda experiment, participant: participant.var.predicted_register == "undefined",
                logic_if_true=CodeBlock(
                    lambda experiment, participant: participant.var.set(
                        "register", random.choice(["low", "high"]))
                ),
                logic_if_false=CodeBlock(lambda experiment, participant: participant.var.set(
                    "register",participant.var.predicted_register)
                                        ),
                fix_time_credit=False
            ),
            practice_singing,
            main_singing,
            questionnaire(),
            InfoPage(Markup(
                f"""
                <h3>Thank you for participating!</h3>
                <hr>
                You have successfully completed the experiment. 
                <br><br>
                <b><b>Completion code</b></b>: we are aware of a problem in Prolific where some participants do not get a completion code at the end of the study. 
                If this is the case, please use the NOCODE option and we will manually send you the full payment. Thank you.
                <hr>
                """
                ), time_estimate=2),
            SuccessfulEndPage(),
        )

    # uncomment for testing
    # test_n_bots = 2
    #
    # def test_experiment(self):
    #     # To run this test, manually change TRIALS_PER_PARTICIPANT to 8 and grid size to 4
    #     super().test_experiment()
    #
    #     nodes = StaticNode.query.filter_by(trial_maker_id="rating_main_experiment").all()
    #
    #     for n in nodes:
    #         n_trials = len(n.infos())
    #         assert n_trials == 1

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = INITIAL_RECRUITMENT_SIZE