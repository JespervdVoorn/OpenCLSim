"""Sequential activity for the simulation."""
import openclsim.core as core

from .base_activities import GenericActivity, StartSubProcesses


class SequentialActivity(GenericActivity, StartSubProcesses):
    """
    SequenceActivity Class forms a specific class.

    This is for executing multiple activities in a dedicated order within a simulation.
    It is a structural activity, which does not require specific resources.

    sub_processes:
        a list of activities to be executed in the provided sequence.
    start_event:
        The activity will start as soon as this event is triggered
        by default will be to start immediately
    """

    def __init__(self, sub_processes, show=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        """Initialization"""

        self.print = show
        self.sub_processes = sub_processes

        for sub_process in self.sub_processes:
            if not sub_process.postpone_start:
                raise Exception(
                    f"In Sequence activity {self.name} the sub_process must have postpone_start=True"
                )

        if not self.postpone_start:
            self.start()

    def start(self):
        self.start_sequential_subprocesses()
        self.register_process(main_proc=self.sequential_process, show=self.print)

    def sequential_process(self, activity_log, env):
        start_time = env.now
        args_data = {
            "env": env,
            "activity_log": activity_log,
            "activity": self,
        }
        yield from self.pre_process(args_data)

        start_sequence = env.now

        activity_log.log_entry(
            t=env.now,
            activity_id=activity_log.id,
            activity_state=core.LogState.START,
        )

        self.start_sequence.succeed()

        for sub_process in self.sub_processes:
            activity_log.log_entry(
                t=env.now,
                activity_id=activity_log.id,
                activity_state=core.LogState.START,
                activity_label={
                    "type": "subprocess",
                    "ref": sub_process.id,
                },
            )

            stop_event = self.parse_expression(
                [
                    {
                        "type": "activity",
                        "state": "done",
                        "name": sub_process.name,
                    }
                ]
            )
            yield stop_event

            activity_log.log_entry(
                t=env.now,
                activity_id=activity_log.id,
                activity_state=core.LogState.STOP,
                activity_label={
                    "type": "subprocess",
                    "ref": sub_process.id,
                },
            )

        activity_log.log_entry(
            t=env.now,
            activity_id=activity_log.id,
            activity_state=core.LogState.STOP,
        )

        args_data["start_preprocessing"] = start_time
        args_data["start_activity"] = start_sequence
        yield from self.post_process(**args_data)

        # work around for the event evaluation
        # this delay of 0 time units ensures that the simpy environment gets a chance to evaluate events
        # which will result in triggered but not processed events to be taken care of before further progressing
        # maybe there is a better way of doing it, but his option works for now.
        yield env.timeout(0)
