import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from duqtools.ids import (IDSMapping, ImasHandle, get_ids_tree, rebase_on_ids,
                          rebase_on_time)
from duqtools.schema.runs import Runs

try:
    default_workdir = sys.argv[1]
except IndexError:
    default_workdir = str(Path.cwd())

st.title('Plot IDS')

with st.sidebar:
    st.header('Input data')
    work_dir = st.text_input('Work directory', default_workdir)
    data_file = st.text_input('Data file', 'runs.yaml')

inp = Path(work_dir) / data_file

if not inp.exists():
    raise ValueError(f'{inp} does not exist!')

if inp.suffix == '.csv':
    df = pd.read_csv(inp, index_col=0)
elif inp.name == 'runs.yaml':
    runs = Runs.parse_file(inp)
    df = pd.DataFrame([run.data_out.dict() for run in runs])
    df.index = [str(run.dirname) for run in runs]
else:
    raise ValueError(f'Cannot open file: {inp}')

with st.expander('IDS data'):
    st.table(df)

prefix = 'profiles_1d/$i'


def ffmt(s):
    return s.replace(prefix + '/', '')


def get_options(a_run):
    a_profile = get_ids_tree(ImasHandle(**a_run), exclude_empty=True)
    return sorted(a_profile.find_by_index(f'{prefix}/.*').keys())


options = get_options(a_run=df.iloc[0])

with st.sidebar:

    default_x_key = options.index(f'{prefix}/grid/rho_tor_norm')
    default_y_val = f'{prefix}/t_i_average'

    x_key = st.selectbox('Select IDS (x)',
                         options,
                         index=default_x_key,
                         format_func=ffmt)

    y_keys = st.multiselect('Select IDS (y)',
                            options,
                            default=default_y_val,
                            format_func=ffmt)

    show_error_bar = st.checkbox(
        'Show errorbar',
        help=(
            'Show standard deviation band around mean y-value. All '
            'y-values are interpolated to put them on a common basis for x.'))


@st.experimental_memo
def get_run_data(row, *, keys, **kwargs):
    """Get data for single run."""
    profile = get_ids_tree(ImasHandle(**row), exclude_empty=True)
    return profile.to_dataframe(*keys, **kwargs)


@st.experimental_memo
def get_data(df, **kwargs):
    """Get and concatanate data for all runs."""
    runs_data = {
        str(name): get_run_data(row, **kwargs)
        for name, row in df.iterrows()
    }

    return pd.concat(runs_data,
                     names=('run',
                            'index')).reset_index('run').reset_index(drop=True)


rebase_on_ids = st.experimental_memo(rebase_on_ids)
rebase_on_time = st.experimental_memo(rebase_on_time)

y_vals = tuple(ffmt(y_key) for y_key in y_keys)
x_val = ffmt(x_key)

for y_val in y_vals:
    st.header(f'{x_val} vs. {y_val}')

    source = get_data(df, keys=(x_val, y_val), prefix='profiles_1d')

    slider = alt.binding_range(min=0, max=source['tstep'].max(), step=1)
    select_step = alt.selection_single(name='tstep',
                                       fields=['tstep'],
                                       bind=slider,
                                       init={'tstep': 0})

    if show_error_bar:
        source = rebase_on_ids(source, base_col=x_val, value_cols=[y_val])
        source = rebase_on_time(source, cols=(x_val, y_val))

        line = alt.Chart(source).mark_line().encode(
            x=f'{x_val}:Q',
            y=f'mean({y_val}):Q',
            color=alt.Color('tstep:N'),
        ).add_selection(select_step).transform_filter(
            select_step).interactive()

        # altair-viz.github.io/user_guide/generated/core/altair.ErrorBandDef
        band = alt.Chart(source).mark_errorband(
            extent='stdev', interpolate='linear').encode(
                x=f'{x_val}:Q',
                y=f'{y_val}:Q',
                color=alt.Color('tstep:N'),
            ).add_selection(select_step).transform_filter(
                select_step).interactive()

        chart = line + band

    else:
        chart = alt.Chart(source).mark_line().encode(
            x=f'{x_val}:Q',
            y=f'{y_val}:Q',
            color=alt.Color('run:N'),
            tooltip='run',
        ).add_selection(select_step).transform_filter(
            select_step).interactive()

    st.altair_chart(chart, use_container_width=True)

with st.form('Save to new IMAS DB entry'):
    a_run = df.iloc[0]

    st.subheader('Template IMAS entry:')

    cols = st.columns(4)

    template = {
        'user': cols[0].text_input('User',
                                   value=a_run.user,
                                   key='user_template'),
        'db': cols[1].text_input('Machine', value=a_run.db, key='db_template'),
        'shot': cols[2].number_input('Shot',
                                     value=a_run.shot,
                                     key='shot_template'),
        'run': cols[3].number_input('Run', value=a_run.run,
                                    key='run_template'),
    }

    template = ImasHandle(**template)

    st.subheader('Target IMAS entry:')

    cols = st.columns(4)

    target = {
        'user':
        cols[0].text_input('User',
                           value=a_run.user,
                           key='user_target',
                           disabled=True),
        'db':
        cols[1].text_input('Machine', value=a_run.db, key='db_target'),
        'shot':
        cols[2].number_input('Shot', value=a_run.shot, key='shot_target'),
        'run':
        cols[3].number_input('Run', step=1, key='run_target'),
    }

    target = ImasHandle(**target)

    submitted = st.form_submit_button('Save')
    if submitted:
        template_data = get_ids_tree(template)

        # pick first time step as basis
        common_basis = template_data[f'profiles_1d/0/{x_val}']

        data = get_data(df, keys=[x_val, *y_vals], prefix='profiles_1d')

        data = rebase_on_ids(data,
                             base_col=x_val,
                             value_cols=y_vals,
                             new_base=common_basis)

        # common_time = [0.0, 0.25, 0.50, 0.75, 1.0]
        common_time = template_data['time']

        # Set to common time basis
        data = rebase_on_time(data,
                              cols=[x_val, *y_vals],
                              new_base=common_time)

        gb = data.groupby(['tstep', x_val])

        agg_funcs = ['mean', 'std']
        agg_dict = {y_val: agg_funcs for y_val in y_vals}

        merged = gb.agg(agg_dict)

        template.copy_ids_entry_to(target)

        core_profiles = target.get('core_profiles')
        ids_mapping = IDSMapping(core_profiles, exclude_empty=False)

        for tstep, group in merged.groupby('tstep'):

            mean = group['t_i_average', 'mean']
            stdev = group['t_i_average', 'std']

            profile = ids_mapping[f'profiles_1d/{tstep}/{y_val}']
            profile[:] = mean

            # This does not work yet, because `*_error_upper` *may* be empty
            # profile_error_upper = ids_mapping[f'profiles_1d/{tstep}/{y_val}_error_upper']
            # profile_error_upper[:] = mean + stdev

        with target.open() as data_entry_target:
            core_profiles.put(db_entry=data_entry_target)

        st.success('Success!')
        st.balloons()
