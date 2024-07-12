import re
from io import BytesIO

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from django.utils.http import urlsafe_base64_encode
from seaborn import FacetGrid

from .local_vars import image_dir_prefix
from .models import Plot

matplotlib.use("Agg")

sns.set_style("whitegrid")  # setting the visualization style
sns.set_context("notebook", font_scale=.9)  # setting the visualization scale


# function to produce a list of explode values for pie charts
def pie_exploder(vals):
    """
    :vals: a list of values to be represented by the pie vedges, sorted in descending order for best results
    :return: a list of explode values for pie charts to only explode very narrow vedges
    :required: numpy
    """
    e = 0.01  # default explode value for all vedges
    explode = np.zeros(len(vals)) + e  # generating default list of uniform explode values with numpy
    i = 0
    for val in vals:
        if val / sum(vals) < 0.03:  # tiny vedge qualification threshold (fraction of the total sum)
            explode[i] = e  # in the first run, default explode value is applied unchanged
            e += .09  # incrementing the explode value starting from the second encountered tiny vedge
        i += 1
    return explode


def plt_savefig(name):
    save_path = f"main/static/main/images/chart_{name}.png"
    plt.savefig(image_dir_prefix + save_path)


def plot_damage_grid(data, palette, title, name):
    x: FacetGrid = sns.relplot(y="Weapon", x="Entity", hue="Damage", size='Damage',
                               data=data,
                               height=4, aspect=3, linewidth=1, edgecolor='gray',
                               palette=palette, sizes=(50, 250)
                               )
    x.ax.tick_params(axis='x', rotation=90)
    plt.title(title)
    save_path = f"main/static/main/images/chart_{name}.png"
    x.savefig(image_dir_prefix + save_path)
    buf = BytesIO()
    x.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf.read()


def run_analysis(data):  # pulling the log as a string from view
    plots = Plot(session_id='a')
    context = {}
    if data:
        lines = data.replace('\\xc2\\xa0', '_').split('\\r\\n')
        lines = [re.sub('<.+?>', '',  # replacing each tag with empty string
                        line.strip()) for line in lines]

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

        # and preparing it for data-framing by turning each entry into a row of cells
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

        warp_prevention = [line for line in combat if line.split(
            ' - ', 1)[1].startswith('Warp ') and ' attempt from ' in line]
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
                                                    :timestamp_length + len(' GJ energy neutralized ') + 5]]
        neuters = {}
        for line in neut:
            sliced = line.split(' - ')
            candidate = sliced[-1]
            if sliced[-2] == candidate:
                if candidate not in neuters.keys():
                    neuters[candidate] = []
                neuters[candidate].append(int(sliced[1]))
        for entity in neuters.keys():
            neuters[entity] = max(neuters.get(entity))

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

        bounty = [line.replace('\xa0', '_') for line in lines if " (bounty) " in line[
                    :timestamp_length + len(' (bounty) ') + 2] and " ISK added to next bounty payout" in line]
        bounty = sum([int(line.split(' (bounty) ', 1)[1].split(' ')[0]) for line in bounty])
        context['bounty'] = bounty

        # VISUALIZATIONS

        if player_weapons:
            # Weapon performance OVERALL - BARS AND PIES

            # data for plotting
            means_per_weapon = dealt_df.groupby(['Weapon']).Damage.mean()  # .sort_values(ascending=False)
            tops_per_weapon = dealt_df.groupby(['Weapon']).Damage.max()  # .sort_values(ascending=False)
            totals_per_weapon = dealt_df.groupby(['Weapon']).Damage.sum().sort_values(ascending=False)
            hits_per_weapon = dealt_df.Weapon.value_counts()

            # bar charts of mean and top damage scores per weapon
            plt.figure(figsize=(10, 3.5), facecolor='white')
            # plt.subplots(layout="constrained")

            plt.subplot(121)
            means_per_weapon.plot(
                kind='bar', ylabel='', title='Overall mean damage per hit',
                color='darkorange', alpha=.85
            )

            plt.subplot(122)
            tops_per_weapon.plot(
                kind='bar', ylabel='', title='Overall top damage per hit',
                color='darkorange', alpha=.85
            )

            name = 'delivered_overall_bars'
            save_path = f"main/static/main/images/chart_{name}.png"
            plt.savefig(image_dir_prefix + save_path, bbox_inches='tight', pad_inches=0.2)

            # Convert the plot to a binary image
            buffer = BytesIO()
            plt.savefig(buffer, format='png')
            image_data = buffer.getvalue()
            # Save the plot to the database
            plots.mean_delivered = image_data
            plots.save()
            plt.close()

            # piecharts of total damage and hit counts per weapon
            plt.figure(figsize=(12.5, 3.5), facecolor='white')
            plt.subplot(121,
                        xlabel=f'Total: {sum(totals_per_weapon)}')  # plotting total damage per weapon
            totals_per_weapon.plot(
                kind='pie', title='Total damage across weapon types', ylabel='',
                # radius=1.1,
                labeldistance=1.2,
                cmap='Oranges_r',
                startangle=45,
                explode=pie_exploder(totals_per_weapon)
            )
            plt.subplot(122,
                        xlabel=f'Total: {sum(hits_per_weapon)}')  # plotting total number of hits per weapon
            hits_per_weapon.plot(
                kind='pie', title='Total hit count across weapon types', ylabel='',
                # radius=.9,
                labeldistance=1.2,
                cmap='Oranges_r',
                startangle=45,
                explode=pie_exploder(hits_per_weapon)
            )
            name = 'delivered_totals_pies'
            save_path = f"main/static/main/images/chart_{name}.png"
            plt.savefig(image_dir_prefix + save_path)
            plt.close()

            # FACET GRIDS:

            # Mean and top damage scores per weapon across all targets
            mean_damage_scores = pd.DataFrame(dealt_df.groupby(['Weapon', 'Entity']).Damage.mean()).sort_values(
                by='Entity').astype('int')
            top_damage_scores = pd.DataFrame(dealt_df.groupby(['Weapon', 'Entity']).Damage.max()).sort_values(
                by='Entity')

            # Mean damage
            plots.mean_delivered = plot_damage_grid(mean_damage_scores, 'Oranges',
                                                    'Mean damage per hit across targets',
                                                    "mean_delivered"
                                                    )
            context['mean_delivered'] = urlsafe_base64_encode(plots.mean_delivered)

            # Top damage
            plots.top_delivered = plot_damage_grid(top_damage_scores, 'Oranges',
                                                   title='Top damage per hit across targets',
                                                   name="top_delivered"
                                                   )

        # RECEIVED DAMAGE
        if enemy_weapons:

            # Bars and pies

            # Data for plotting
            means_per_enemy = incoming_df.groupby(['Entity']).Damage.mean()
            tops_per_enemy = incoming_df.groupby(['Entity']).Damage.max()
            totals_per_enemy = incoming_df.groupby(['Entity']).Damage.sum().sort_values(ascending=False)
            hits_per_enemy = incoming_df.Entity.value_counts()

            #  bar charts of mean and top damage taken from each enemy

            plt.figure(figsize=(11, 4))
            plt.subplot(121)
            means_per_enemy.plot(
                kind='bar', ylabel='', title='Overall mean damage per enemy hit',
                color='darkred', alpha=.85
            )
            plt.subplot(122)
            tops_per_enemy.plot(
                kind='bar', ylabel='', title='Overall top damage per enemy hit',
                color='darkred', alpha=.85
            )

            name = 'received_overall_bars'
            save_path = f"main/static/main/images/chart_{name}.png"
            plt.savefig(image_dir_prefix + save_path, bbox_inches='tight', pad_inches=0.2)
            plt.close()

            # piecharts of total damage and hit counts from each enemy

            height = 3.5  # overall for the figure
            radius = 1  # for each pie
            if len(enemies) > 11:  # to provide more space for labels
                height = 5
                radius = .7

            plt.figure(figsize=(12, height), facecolor='white')
            plt.subplot(121,
                        xlabel=f'Total: {sum(totals_per_enemy)}')  # plotting total damage per enemy
            totals_per_enemy.plot(
                kind='pie', title='Total incoming damage across kinds of enemies', ylabel='',
                radius=radius,
                labeldistance=1.2,
                cmap='Reds_r',
                startangle=45,
                explode=pie_exploder(totals_per_enemy)
            )
            plt.subplot(122,
                        xlabel=f'Total: {sum(hits_per_enemy)}')  # plotting total number of hits per enemy
            hits_per_enemy.plot(
                kind='pie', title='Total incoming hit count across kinds of enemies', ylabel='',
                radius=radius,
                labeldistance=1.2,
                cmap='Reds_r',
                startangle=45,
                explode=pie_exploder(hits_per_enemy)
            )

            name = 'received_totals_pies'
            save_path = f"main/static/main/images/chart_{name}.png"
            plt.savefig(image_dir_prefix + save_path)
            plt.close()

        # Mean, top, and total incoming damage scores per enemy weapon across all kinds of enemies

            mean_damage_scores = pd.DataFrame(incoming_df.groupby(['Weapon', 'Entity']).Damage.mean()).sort_values(
                by='Entity').astype(int)
            top_damage_scores = pd.DataFrame(incoming_df.groupby(['Weapon', 'Entity']).Damage.max()).sort_values(
                by='Entity')
            totals = pd.DataFrame(incoming_df.groupby(['Weapon', 'Entity']).Damage.sum()).sort_values(by='Entity')

            # Mean damage
            plots.mean_received = plot_damage_grid(mean_damage_scores, 'Reds',
                                                   'Mean incoming damage per hit across enemies',
                                                   "mean_received"
                                                   )

            # Top damage
            plots.top_received = plot_damage_grid(top_damage_scores, 'Reds',
                                                  'Top incoming damage per hit across enemies',
                                                  "top_received"
                                                  )

            # Total damage
            plots.total_received = plot_damage_grid(totals, 'Reds',
                                                    'Total incoming damage across enemies and their weapons',
                                                    "total_received"
                                                    )

            # plots.save()

            # context['plots'] = plots

    return context
