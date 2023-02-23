import re
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
matplotlib.use("Agg")


sns.set_style("whitegrid")  # setting the visualization style
sns.set_context("notebook", font_scale=.9)  # setting the visualization scale


def save_uploaded_file(f):
    with open('analyzer/temp/gamelog.txt', 'wb') as destination:
        for chunk in f.chunks():
            destination.write(chunk)
    return True


def run_analysis(data):  # pulling the log as a string from view
    context = {}
    if data:
        lines = data.replace('\\xc2\\xa0', '_').split('\\r\\n')
        lines = [re.sub('<.+?>', '',  # replacing each tag with empty string
                        line.strip()
                        ) for line in lines]

        context['lines'] = lines  # log as a list of lines back to view
        context['processed'] = True

        lines = [line for line in lines if line.startswith('[ ')]  # taking only timestamped lines
        lines = [line.strip('[ ').replace(' ]', '') for line in lines]  # cleaning the timestamps

        # Getting a list of all combat related entries:
        timestamp_length = len('2022.11.01 08:29:30')
        combat = [line for line in lines if ' (combat) ' in line[:timestamp_length + len(' (combat) ') + 2]]
        combat = [line.replace('(combat)', '-', 1) for line in
                  combat]  # also replacing '(combat)' with '-' to use as column separator

        # Getting a list of damage-exchange entries

        hits = [
            line for line in combat if (
                                           line.endswith('- Grazes')) or (  # hit quality tokens
                                           line.endswith('- Hits')) or (
                                           line.endswith('- Glances Off')) or (
                                           line.endswith('- Smashes')) or (
                                           line.endswith('- Penetrates')) or (
                                           line.endswith('- Wrecks'))
        ]

        # and preparing it for dataframing by turning each entry into a row of cells
        # installing column separators '-' and performing the split
        hits = [line.replace(' to ', ' - to - ').replace(' from ', ' - from - ').split(' - ') for line in hits]
        # inserting 'Unknown' for missing enemy weapon data
        for entry in hits:
            if len(entry) != 6:
                entry.insert(-1, 'Unknown')

        columns = ['Time', 'Damage', 'Direction', 'Entity', 'Weapon', 'Token']
        # Creating the damage exchange dataframe
        hits_df = pd.DataFrame(data=hits, columns=columns)
        hits_df.Damage = hits_df.Damage.astype('int')  # Casting the damage scores to integer

        # Warp prevention

        warp_prevention = [line for line in combat if line.split(' - ', 1)[1]
        .startswith('Warp ') and ' attempt from ' in line]
        warp_prevention_df = pd.DataFrame(
            data=[line.replace("from", "-").replace("to", "-").replace('attempt ', '')
                  .rstrip('!').split(' - ') for line in warp_prevention],
            columns=['Time', 'Action', 'Issuer', 'Recipient']
        )
        received = warp_prevention_df[warp_prevention_df.Recipient == "you"].drop(columns="Recipient")
        incoming_warp_prevention = {}
        for action in received.Action.unique():
            incoming_warp_prevention[action] = ', '.join(received[received.Action == action].Issuer.unique().tolist())

        context['incoming_warp_prevention'] = incoming_warp_prevention

        # Ewar

        neut = [line.replace('GJ energy neutralized', '-', 1
                             ) for line in combat if ' GJ energy neutralized ' in line[
                                                                                  :timestamp_length + len(
                                                                                      ' GJ energy neutralized ') + 5]]
        neuters = {}
        for line in neut:
            sliced = line.split(' - ')
            candidate = sliced[-1]
            if sliced[-2] == candidate:
                if candidate not in neuters.keys():
                    neuters[candidate] = []
                neuters[candidate].append(int(sliced[1]))
        for entity in neuters.keys():
            neuters[entity] = max(neuters[entity])

        context['neuters'] = neuters

        # Summary stats

        # Dealt damage
        dealt_df = hits_df.loc[hits_df.Direction == 'to']
        targets = dealt_df.Entity.unique().tolist()
        context['targets'] = targets  # list of targets back to view
        player_weapons = dealt_df.Weapon.unique().tolist()
        context['player_weapons'] = player_weapons  # list of player weapons back to view

        # Incoming damage
        incoming_df = hits_df.loc[hits_df.Direction == 'from']
        enemies = incoming_df.Entity.unique().tolist()
        context['enemies'] = enemies  # list of enemies back to view
        enemy_weapons = incoming_df.Weapon.unique().tolist()
        context['enemy_weapons'] = enemy_weapons

        # bounty = sum([int(line.split(' (bounty) ', 1)[1].split(' ')[0]
        #     ) for line in lines if " ] (bounty) " in line and " ISK added to next bounty payout" in line])
        bounty = [line.replace('\xa0', '_') for line in lines if " (bounty) " in line[
                                                                                 :timestamp_length + len(
                                                                                     ' (bounty) ') + 2] and " ISK added to next bounty payout" in line]
        bounty = sum([int(line.split(' (bounty) ', 1)[1].split(' ')[0]) for line in bounty])
        context['bounty'] = bounty

        # Visualizing
        if player_weapons:
            # Plotting mean and top damage scores per weapon across all targets
            mean_damage_scores = pd.DataFrame(dealt_df.groupby(['Weapon', 'Entity']).Damage.mean()).sort_values(
                by='Entity').astype('int')
            top_damage_scores = pd.DataFrame(dealt_df.groupby(['Weapon', 'Entity']).Damage.max()).sort_values(
                by='Entity')

            # Mean damage
            x = sns.relplot(y="Weapon", x="Entity", hue="Damage", size='Damage',
                            data=mean_damage_scores,
                            height=4, aspect=3, linewidth=1, edgecolor='gray',
                            palette='Oranges', sizes=(50, 200)
                            )
            x.ax.tick_params(axis='x', rotation=90)
            plt.title('Mean damage per hit across targets')
            x.savefig("main/static/main/images/mean_delivered.png")

            # Top damage
            x = sns.relplot(y="Weapon", x="Entity", hue="Damage", size='Damage',
                            data=top_damage_scores,
                            height=4, aspect=3, linewidth=1, edgecolor='gray',
                            palette='Oranges', sizes=(50, 200)
                            )
            x.ax.tick_params(axis='x', rotation=90)
            plt.title('Top damage per hit across targets')
            x.savefig("main/static/main/images/top_delivered.png")

        if enemy_weapons:
            # Plotting mean, top, and total incoming damage scores per enemy weapon across all kinds of enemies
            mean_damage_scores = pd.DataFrame(incoming_df.groupby(['Weapon', 'Entity']).Damage.mean()).sort_values(
                by='Entity').astype(int)
            top_damage_scores = pd.DataFrame(incoming_df.groupby(['Weapon', 'Entity']).Damage.max()).sort_values(
                by='Entity')
            totals = pd.DataFrame(incoming_df.groupby(['Weapon', 'Entity']).Damage.sum()).sort_values(by='Entity')

            # Mean damage
            x = sns.relplot(y="Weapon", x="Entity", hue="Damage", size='Damage',
                            data=mean_damage_scores,
                            height=4, aspect=3,
                            palette='Reds', sizes=(100, 250)
                            )
            x.ax.tick_params(axis='x', rotation=90)
            plt.title('Mean incoming damage per hit across enemies')
            x.savefig("main/static/main/images/mean_received.png")

            # Top damage
            x = sns.relplot(y="Weapon", x="Entity", hue="Damage", size='Damage',
                            data=top_damage_scores,
                            height=4, aspect=3,
                            palette='Reds', sizes=(100, 250)
                            )
            x.ax.tick_params(axis='x', rotation=90)
            plt.title('Top incoming damage per hit across enemies')
            x.savefig("main/static/main/images/top_received.png")

            # Total damage
            x = sns.relplot(y="Weapon", x="Entity", hue="Damage", size='Damage',
                            data=totals,
                            height=4, aspect=3,
                            palette='Reds', sizes=(100, 250)
                            )
            x.ax.tick_params(axis='x', rotation=90)
            plt.title('Total incoming damage across enemies and their weapons')
            x.savefig("main/static/main/images/total_received.png")

    return context
