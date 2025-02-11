'''
Performs a clean up of the current folder, removing specific run subfolders and their appearance in the runs.json file.

Usage:
    python cleanup.py [options] [run_names]

Options:
    --renumber, -r            renumber the runs in the runs.json file, basically filling the gaps in the runs.json file. This also renames the run subfolders.
    --ask-confirmation, -a    ask for confirmation before removing a run. If the run is not FAILED, you will be prompted for confirmation anyways.
    --all, -A                 remove all FAILED runs

If you didn't use the --all option, you can provide a list of run names to remove. Each run name can either be the number of the run or its full name
'''

import shutil
import sys
import Learn2_new as ln
ut = ln.ut

def change_run_id(name, new_run_id):
    if ln.arg_sep in name:
        run_id, name = name.split(ln.arg_sep, 1)
    else:
        run_id, name = name, ''
    flag = run_id[0]
    if flag.isdigit():
        flag = ''
    return f"{flag}{new_run_id}{f'{ln.arg_sep}{name}' if name else ''}"

def remove_run(runs, k, ask_confirmation=False):
    v = runs[str(k)]
    if v['status'] != 'FAILED' or ask_confirmation:
        o = input(f"Are you sure you want to remove {v['status']} run {v['name']}? (Y/[n]) ")
        if o != 'Y':
            print('Keeping the run')
            return runs
    v = runs.pop(str(k))
    shutil.rmtree(f"./{v['name']}")
    return runs

def remove_runs(run_names, renumber=False, ask_confirmation=False):
    runs = ut.json2dict('./runs.json')

    for run_name in run_names:
        try:
            k = int(run_name)
            runs = remove_run(runs, k, ask_confirmation=ask_confirmation)
        except ValueError:
            for (k,v) in runs.items():
                if v['name'] == run_name:
                    runs = remove_run(runs, k, ask_confirmation=ask_confirmation)
                    break
    ut.dict2json(runs, './runs.json')

    if renumber:
        renumber_runs()

def renumber_runs():
    runs = ut.json2dict('./runs.json')
    runs_new = {}
    for i,(k,v) in enumerate(runs.items()):
        if i == int(k):
            runs_new[k] = v
            continue
        name = change_run_id(v['name'], i)
        shutil.move(f"./{v['name']}", f"./{name}")
        v['name'] = name
        runs_new[str(i)] = v
    ut.dict2json(runs_new, './runs.json')


def clean_all(renumber=False):
    runs = ut.json2dict('./runs.json')
    runs_new = {}
    removed_runs = 0
    for i,(k,v) in enumerate(runs.items()):
        new_i = i - removed_runs
        if v['status'] == 'FAILED':
            shutil.rmtree(f"./{v['name']}")
            print(f'Removing {v["name"]}')
            removed_runs += 1
        elif renumber and new_i != int(k):
            name = change_run_id(v['name'], new_i)
            shutil.move(f"./{v['name']}", f"./{name}")
            v['name'] = name
            runs_new[str(new_i)] = v
        else:
            runs_new[k] = v
    ut.dict2json(runs_new, './runs.json')


if __name__ == '__main__':
    args = sys.argv[1:]

    do_renumber=False
    ask_confirmation=False
    do_clean_all=False
    runs_to_remove = []

    print('\n\n\n')

    if len(args) == 0:
        print(__doc__)
        sys.exit(0)

    for a in args:
        if a.startswith('--'):
            if a == '--renumber':
                do_renumber = True
            elif a == '--ask-confirmation':
                ask_confirmation = True
            elif a == '--all':
                do_clean_all = True
            else:
                print(f'Unknown argument {a}')
                sys.exit(1)
        elif a.startswith('-'):
            if 'r' in a:
                do_renumber = True
            if 'a' in a:
                ask_confirmation = True
            if 'A' in a:
                do_clean_all = True
        else:
            runs_to_remove.append(a)


    if do_clean_all:
        clean_all(renumber=do_renumber)
    elif len(runs_to_remove):
        remove_runs(runs_to_remove, renumber=do_renumber, ask_confirmation=ask_confirmation)
    elif do_renumber:
        renumber_runs()
    else:
        print('Doing nothing: see documentation.')
        print(__doc__)
        