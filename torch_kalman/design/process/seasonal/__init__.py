from torch_kalman.design.nn_input import CurrentTime
from torch_kalman.design.nn_output import NNOutput, NNDictOutput
from torch_kalman.design.process import Process
from torch_kalman.design.process.seasonal.nn_modules import InitialSeasonStateNN, SeasonDurationNN
from torch_kalman.utils.utils import nonejoin
from torch_kalman.design.state import State


class Seasonal(Process):
    def __init__(self, id_prefix, std_dev, period, duration, season_start, time_input_name, sep="_"):
        # input:
        self.nn_input = CurrentTime(name=time_input_name, num_dims=3)

        # define states, their std-dev, and initial-values:
        self.nn_module_initial = InitialSeasonStateNN(period=period, duration=duration)
        pad_n = len(str(period))
        states = []
        for i in range(period):
            season = str(i).rjust(pad_n, "0")
            this_state = State(id=nonejoin([id_prefix, 'season', season], sep),
                               std_dev=std_dev if i == 0 else 0.0,
                               initial_value=NNOutput(nn_module=self.nn_module_initial, nn_output_idx=i))
            states.append(this_state)

        # define transitions:
        self.nn_module_season_duration = SeasonDurationNN(period=period, duration=duration, season_start=season_start)
        # for the first state, only need to define two transitions:
        states[0].add_transition(to_state=states[1],
                                 multiplier=NNDictOutput(self.nn_module_season_duration, nn_output_name='to_next'))
        states[0].add_transition(to_state=states[0],
                                 multiplier=NNDictOutput(self.nn_module_season_duration,
                                                         nn_output_name='from_first_to_first'))

        # for the rest, need to define three transitions:
        for i in range(1, period):
            if (i + 1) < period:
                # when transitioning:
                states[i].add_transition(to_state=states[i + 1],
                                         multiplier=NNDictOutput(self.nn_module_season_duration, nn_output_name='to_next'))
                states[i].add_transition(to_state=states[0],
                                         multiplier=NNDictOutput(self.nn_module_season_duration, nn_output_name='to_first'))

            # when not transitioning:
            states[i].add_transition(to_state=states[i],
                                     multiplier=NNDictOutput(self.nn_module_season_duration, nn_output_name='to_self'))

        super(Seasonal, self).__init__(states)

    def add_modules_to_design(self, design, known_to_super=False):
        design.add_nn_module(type='initial_state',
                             nn_module=self.nn_module_initial,
                             nn_input=self.nn_input,
                             known_to_super=known_to_super)
        design.add_nn_module(type='transition',
                             nn_module=self.nn_module_season_duration,
                             nn_input=self.nn_input,
                             known_to_super=known_to_super)

    @property
    def observable(self):
        return self.states[0]