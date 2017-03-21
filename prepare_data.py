from os.path import join as pj
import os
import pandas as pd
import numpy as np

base_dir = os.path.dirname(__file__)
data_dir = pj(base_dir, 'data')

# ====================== Import data ======================
active_days = pd.read_csv(pj(data_dir, 'active_days.csv'), parse_dates=['date'])
users = pd.read_csv(pj(data_dir, 'users.csv'))

cycles = pd.read_csv(pj(data_dir, 'cycles.csv'), parse_dates=['cycle_start'])
cycles0 = pd.read_csv(pj(data_dir, 'cycles0.csv'), parse_dates=['cycle_start'])

# Train on this
tracking = pd.read_csv(pj(data_dir, 'tracking.csv'), parse_dates=['date'])
# Test on this
tracking_test = pd.read_csv(pj(data_dir, 'labels.csv'))


# ================  Feature engineer a user ================
symptoms_of_interest = [
    'happy', 'pms', 'sad', 'sensitive_emotion',
    'energized', 'exhausted', 'high_energy', 'low_energy',
    'cramps', 'headache', 'ovulation_pain', 'tender_breasts',
    'acne_skin', 'good_skin', 'oily_skin', 'dry_skin'
]

other_symptoms = list(set(tracking.symptom.unique()) - set(symptoms_of_interest))
list_of_symptoms = symptoms_of_interest + other_symptoms
ordered_symptoms = {s: i for i, s in enumerate(list_of_symptoms)}
symptoms_of_interest_dict = {code:symptom for symptom, code in ordered_symptoms.items() if code < 16}
N_symptoms = len(ordered_symptoms)

tracking['symptom_code'] = tracking.symptom.map(lambda s: ordered_symptoms[s])


def transform_user(user_id):
    #out = tracking[tracking.user_id == user_id]
    out = np.where(tracking.user_id == user_id)    
    out.loc[:, 'absolute_day'] = (out.date.dt.date - out.date.dt.date.min()).dt.days + 1
    out = pd.merge(out, cycles[cycles.user_id == user_id], on=["cycle_id", "user_id"])

    out_sequence = np.zeros(
        (
            out.absolute_day.max(),
            N_symptoms + 1
        )
    )
    out_sequence[:, -1] = range(1, out_sequence.shape[0] + 1)
    for _, row in out.iterrows():
        out_sequence[row['absolute_day'] - 1, row['symptom_code']] = 1
    return out_sequence


def transform_users(user_ids):
    return np.vstack(
        [transform_user(user_id)
         for user_id in user_ids]
    )


def get_sample_of_users(n, min_tracking_count=20):
    symptom_tracking_count = tracking.user_id.value_counts()
    interesting_users = symptom_tracking_count[symptom_tracking_count > min_tracking_count]

    return list(
        interesting_users.sample(n).index
    )


def expand_cycle(cycle):
    dates = pd.date_range(start=cycle.cycle_start, periods=cycle.cycle_length).tolist()
    period = np.zeros(cycle.cycle_length, dtype=np.int8)
    period[:cycle.period_length] = 1
    day_in_cycle = np.arange(1, cycle.cycle_length + 1, dtype=np.int8)

    index = pd.MultiIndex.from_tuples(
        tuples=list(zip([cycle.user_id] * int(cycle.cycle_length), dates)),
        # [(cycle.user_id, cycle.cycle_id)] * int(cycle.cycle_length),
        names=["user_id", "date"]
    )

    return pd.DataFrame(
        data=list(zip([cycle.cycle_id] * int(cycle.cycle_length), day_in_cycle, period)),
        index=index,
        columns=['cycle_id', 'day_in_cycle', 'period']
    )


if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-N_users', default=10, type=int,
        help='How many users to sequence')

    args = parser.parse_args()

    if args.N_users > 0:
        sample_of_users = get_sample_of_users(args.N_users)
        sequence = transform_users(sample_of_users)
