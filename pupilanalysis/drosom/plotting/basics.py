'''
Most commonly needed functions to plot the data.
'''

import os
import math
import copy

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import proj3d
import mpl_toolkits.axes_grid1
import matplotlib.image
from scipy.ndimage import rotate
import PIL

from .common import (
        vector_plot,
        surface_plot,
        add_rhabdomeres,
        add_line,
        plot_2d_opticflow
        )
from pupilanalysis.directories import CODE_ROOTDIR
from pupilanalysis.drosom.optic_flow import field_error
from pupilanalysis.coordinates import rotate_vectors

plt.rcParams.update({'font.size': 12})

EYE_COLORS = {'right': 'blue', 'left': 'red'}
REPEAT_COLORS = ['green', 'orange', 'pink']


DEFAULT_ELEV = 10
DEFAULT_AZIM = 70
DEFAULT_FIGSIZE = (16,9)

def plot_1d_magnitude(manalyser, image_folder=None, i_repeat=None,
        mean_repeats=False, mean_imagefolders=False, mean_eyes=False,
        color_eyes=False, gray_repeats=False, show_mean=False, show_std=False,
        show_label=True, milliseconds=False, microns=False,
        label="EYE-ANGLE-IREPEAT", ax=None):
    '''
    Plots 1D displacement magnitude over time, separately for each eye.
    
    Arguments
    ---------
    manalyser : object
        MAnalyser object instance
    image_folder : string or None
        Image folder to plot the data from. If None (default), plot all image folders.
    mean_repeats : bool
        Wheter to take mean of the repeats or plot each repeat separately
    mean_imagefolders : bool
        If True and image_folder is None (plotting all image folders), takes the mean
        of all image folders.
    mean_eyes : bool
        Wheter to take a mean over the left and right eyes
    label : string
        Label to show. If None, no label. Otherwise
        EYE gets replaced with eye
        ANGLE gets replaced by image folder name
        IREPEAT gets reaplaced by the number of repeat
    
    Returns
        ax
            Matplotlib axes
        traces
            What has been plotted
        N_repeats
            The total number of repeats (independent of i_repeat)
    '''
    
    def get_x_yscaler(mag_rep_i):    
        # FIXME Pixel size and fs should be read from the data
        pixel_size = 0.816
        fs = 100
        N = len(mag_rep_i)

        if milliseconds:
            # In milliseconds
            X = 1000* np.linspace(0, N/fs, N)
        else:
            X = np.arange(N)
        
        if microns:
            yscaler = pixel_size
        else:
            yscaler = 1
        
        return X, yscaler
    
    X = None
    yscaler = None

    if ax is None:
        fig, ax = plt.subplots()

    if mean_eyes:
        eyes = [None]
    else:
        eyes = manalyser.eyes

    N_repeats = 0
    traces = []
   

    for eye in eyes:
        magtraces = manalyser.get_magnitude_traces(eye, image_folder=image_folder,
                mean_repeats=mean_repeats, mean_imagefolders=mean_imagefolders)
        
        for angle, repeat_mags in magtraces.items():
            
            if X is None or yscaler is None:
                X, yscaler = get_x_yscaler(repeat_mags[0])


            for _i_repeat, mag_rep_i in enumerate(repeat_mags):
                
                N_repeats += 1
                
                if i_repeat is not None and _i_repeat != i_repeat:
                    continue
                
                
                if label:
                    if eye is None:
                        eyename = '+'.join(manalyser.eyes)
                    else:
                        eyename = eye
                    _label = label.replace('EYE', eyename).replace('ANGLE', str(angle)).replace('IREPEAT', str(_i_repeat))
                else:
                    _label = ''
                
                Y = yscaler * mag_rep_i

                if color_eyes:
                    ax.plot(X, Y, label=_label, color=EYE_COLORS.get(eye, 'green'))
                elif gray_repeats:
                    ax.plot(X, Y, label=_label, color='gray')
                else:
                    ax.plot(X, Y, label=_label)
                
                traces.append(Y)
    
    meantrace = np.mean(traces, axis=0)
    if show_mean:
        ax.plot(X, meantrace, label='mean-of-all', color='black', lw=3)

    if show_std:
        ax.plot(X, meantrace+np.std(traces, axis=0), '--', label='std-of-mean-of-all', color='black', lw=2)
        ax.plot(X, meantrace-np.std(traces, axis=0), '--', color='black', lw=2)
    
    if label and show_label:
        ax.legend(fontsize='xx-small', labelspacing=0.1, ncol=int(len(traces)/10)+1, loc='upper left')    
    

    if milliseconds:
        ax.set_xlabel('Time (ms)')
    else:
        ax.set_xlabel('Frame')

    if microns:
        ax.set_ylabel('Displacement magnitude (µm)')
    else:
        ax.set_ylabel('Displacement magnitude (pixels)')


    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)

    return ax, traces, N_repeats



def _set_analyser_attributes(analyser, skip_none=True, raise_errors=False, **kwargs):
    '''
    Sets attributes to manalyser.
    Raises AttributeError if the analyser does not have the attribute beforehand.

    Returns a dictionary of the original parameters
    '''
    for key, value in kwargs:
        if value is not None or skip_none == False:
            if hasattr(analyser, key):
                setattr(analyser, key, value)
            elif raise_errors:
                raise AttributeError('{} has no attribute {} prior setting'.format(anlayser, key))


def plot_3d_vectormap(manalyser, arrow_rotations = [0],
        guidance=False, draw_sphere=False, hide_behind=True, rhabdomeres=True,
        elev=None, azim=None, color=None, repeats_separately=False, vertical_hardborder=True,
        i_frame=0,
        pitch_rot=None, roll_rot=None, yaw_rot=None,
        animation=None, animation_type=None, animation_variable=None,
        ax=None, **kwargs):
    '''
    Plot a 3D vectormap, where the arrows point the movement or feature directions.
    
    arrow_rotations : list of int
        Radial rotation of the vectors
    guidance : bool
        Draw ventral/dorsal/left/right axes
    draw_sphere : bool
        Draw a 

    arrows : bool
        If False, draw lines instead (only OAnalyser)
    rhabdomeres : bool
        If True, draw rhadbomeres (only OAnalyser)

    **kwargs to vector_plot
    '''

    colors = EYE_COLORS
    plot_rhabdomeres = True
    
    manalyser_type = 'MAnalyser'

    if manalyser.__class__.__name__ == 'OAnalyser' and len(arrow_rotations) == 1 and arrow_rotations[0] == 0:
        manalyser_type = 'OAnalyser'
    elif manalyser.__class__.__name__ == 'MAverager':
        if all([partanalyser.__class__.__name__ == 'OAnalyser' for partanalyser in manalyser.manalysers]):
            manalyser_type = 'OAnalyser'
    elif manalyser.__class__.__name__ == 'FAnalyser':
        colors = ['darkviolet']*5
        if animation_type != 'rotate_arrows':
            i_frame = 0
        
    _set_analyser_attributes({'pitch_rot': pitch_rot,
        'roll_rot': roll_rot, 'yaw_rot': yaw_rot})


    if manalyser_type == 'OAnalyser':
        colors = REPEAT_COLORS
        i_frame = 0
        
        # OAnalyser specific for Drosophila; Assuming that R3-R6 line is
        # analysed, let's also draw the line from R3 to R1.
        if arrow_rotations[0] == 0 and len(arrow_rotations) == 1:
            arrow_rotations.append(29)

    if ax is None:
        fig = plt.figure(figsize=DEFAULT_FIGSIZE)
        ax = fig.add_subplot(111, projection='3d')
    
    vectors = {}

    original_rotation = manalyser.vector_rotation

    if animation_type == 'rotate_plot':
        elev, azim = animation_variable

    if hide_behind and azim is not None and elev is not None:
        camerapos = (elev, azim)
    else:
        camerapos = False
    
    # For OAnalyser, when rhabdomeres is set True,
    # plot the rhabdomeres also
    if manalyser_type == 'OAnalyser' and rhabdomeres:
        manalyser.vector_rotation = 0
        for eye in manalyser.eyes:

            vectors_3d = manalyser.get_3d_vectors(eye, correct_level=True,
                    repeats_separately=repeats_separately,
                    strict=True, vertical_hardborder=vertical_hardborder)

            if eye == 'left':
                mirror_lr = True
            else:
                mirror_lr = False

            for point, vector in zip(*vectors_3d):
                add_rhabdomeres(ax, *point, *vector,
                        mirror_lr=mirror_lr, mirror_bf='auto',
                        camerapos=camerapos,
                        resolution=9, edgecolor=None, facecolor='gray')



    for i_rotation, rotation in enumerate(arrow_rotations):

        for eye in manalyser.eyes:
            if isinstance(colors, dict):
                colr = colors[eye]
            elif isinstance(colors, list):
                colr = colors[i_rotation]
            
            # Set arrow/vector rotation
            if rotation is not None or rotation != 0:
                manalyser.vector_rotation = rotation
            
            vectors_3d = manalyser.get_3d_vectors(eye, correct_level=True,
                    repeats_separately=repeats_separately,
                    strict=True, vertical_hardborder=vertical_hardborder)
            
            if manalyser_type == 'OAnalyser' and rhabdomeres:
                
                for point, vector in zip(*vectors_3d):
                    add_line(ax, *point, *vector, camerapos=camerapos, color=REPEAT_COLORS[i_rotation])
            else:
                vector_plot(ax, *vectors_3d, color=colr,
                        guidance=guidance,
                        draw_sphere=draw_sphere,
                        camerapos=camerapos,
                        i_pulsframe=i_frame,
                        **kwargs
                        )
               
            vectors[eye] = vectors_3d
           
    manalyser.vector_rotation = original_rotation

    
    ax.set_xlim3d((-1,1))
    ax.set_ylim3d((-1,1))
    ax.set_zlim3d((-1,1))
    ax.set_box_aspect((1, 1, 1)) 
    
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_zlabel('z')
    
    if azim is None and elev is None:
        ax.view_init(elev=DEFAULT_ELEV, azim=DEFAULT_AZIM)
    else:
        ax.view_init(elev=elev, azim=azim)

    return ax, vectors


def plot_3d_differencemap(manalyser1, manalyser2, ax=None,
        elev=DEFAULT_ELEV, azim=DEFAULT_AZIM, colinear=True,
        colorbar=True, colorbar_text=True, colorbar_ax=None, reverse_errors=False,
        colorbar_text_positions=[[1.1,0.95,'left', 'top'],[1.1,0.5,'left', 'center'],[1.1,0.05,'left', 'bottom']],
        i_frame=0, arrow_rotations=[0], pitch_rot=None, yaw_rot=None, roll_rot=None):
    '''
    Plots 3d heatmap presenting the diffrerence in the vector orientations
    for two analyser objects, by putting the get_3d_vectors of both analysers
    to field_error and making a surface plot.
    
    Notes:
        - Errors (differences) are calculated at manalyser1's points.
        - arrow_rotations, pitch_rot only affects manalyser2

    manalyser1, manalyser2 : object
        Analyser objects to plot the difference with 3d vectors
    ax : object or None
        Matplotlib Axes object
    colorbar : bool
        Whether to add the colors explaining colorbar
    colorbar_text: bool
        Wheter to add the text annotations on the colorbar
    colorbar_ax : object
        Optional Axes where to put the colorbar
    arrow_rotations : list
        Arrow rotations, for the second manalyser
    i_frame : int
        Neglected here
    '''
    
    if ax is None:
        fig = plt.figure(figsize=DEFAULT_FIGSIZE)
        ax = fig.add_subplot(111, projection='3d')
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set_zlabel('z')
     
    if arrow_rotations:
        original_rotation = manalyser2.vector_rotation
        manalyser2.vector_rotation = arrow_rotations[0]
    
    if pitch_rot is not None:
        manalyser2.pitch_rot = pitch_rot
    if yaw_rot is not None:
        manalyser2.yaw_rot = yaw_rot
    if roll_rot is not None:
        manalyser2.roll_rot = roll_rot
    

    all_errors = []
    for eye in manalyser1.eyes:
        vectors = []
        points = []

        for manalyser in [manalyser1, manalyser2]:
            
            vectors_3d = manalyser.get_3d_vectors(eye, correct_level=True,
                repeats_separately=False,
                strict=True, vertical_hardborder=True)
 
            points.append(vectors_3d[0])
            vectors.append(vectors_3d[1])
       
        # Errors at the points[0]
        errors = field_error(points[0], vectors[0], points[1], vectors[1], colinear=colinear)
        
        if reverse_errors:
            errors = 1-errors

        all_errors.append(errors)
        
        if eye=='left':
            all_phi_points = [np.linspace(math.pi/2, 3*math.pi/2, 50)]
        else:
            all_phi_points = [np.linspace(0, math.pi/2, 25), np.linspace(3*math.pi/2, 2*math.pi,25)]

        for phi_points in all_phi_points:
            m = surface_plot(ax, points[0], errors, phi_points=phi_points)
    
    errors = np.concatenate(all_errors)

    ax.view_init(elev=elev, azim=azim)

    # COLORBAR
    if colorbar and getattr(ax, 'differencemap_colorbar', None) is None:

        if colorbar_ax is None:
            cbox = ax.get_position()
            cbox.x1 -= abs(cbox.x1 - cbox.x0)/10
            cbox.x0 += abs((cbox.x1 - cbox.x0))/1.1
            cbox.y0 -= 0.18*abs(cbox.y1-cbox.y0)
            cax = ax.figure.add_axes(cbox)
        else:
            cax = colorbar_ax
        
        ax.differencemap_colorbar = [cax, plt.colorbar(m, cax)]
    
        # COLORBAR INFO TEXT
        if colorbar_text:
            cax = ax.differencemap_colorbar[0]
            #text_x = 1+0.1
            #ha = 'left'
            if colinear:
                cax.text(colorbar_text_positions[0][0], colorbar_text_positions[0][1],
                        'Collinear',
                        ha=colorbar_text_positions[0][2], va=colorbar_text_positions[0][3],
                        transform=cax.transAxes)
                cax.text(colorbar_text_positions[2][0], colorbar_text_positions[2][1], 
                        'Perpendicular',
                        ha=colorbar_text_positions[2][2], va=colorbar_text_positions[2][3],
                        transform=cax.transAxes)
            else:
                cax.text(colorbar_text_positions[0][0], colorbar_text_positions[0][1],
                        'Matching',
                        ha=colorbar_text_positions[0][2], va=colorbar_text_positions[0][3],
                        transform=cax.transAxes)
                cax.text(colorbar_text_positions[1][0], colorbar_text_positions[1][1],
                        'Perpendicular',
                        ha=colorbar_text_positions[1][2], va=colorbar_text_positions[1][3],
                        transform=cax.transAxes)
                cax.text(colorbar_text_positions[2][0], colorbar_text_positions[2][1], 
                        'Opposing',
                        ha=colorbar_text_positions[2][2], va=colorbar_text_positions[2][3],
                        transform=cax.transAxes)
            
            cax.set_axis_off()

    if arrow_rotations:
        manalyser2.vector_rotation = original_rotation
    
    ax.set_xlim3d((-1,1))
    ax.set_ylim3d((-1,1))
    ax.set_zlim3d((-1,1))
    ax.set_box_aspect((1, 1, 1)) 
 
    return ax, errors


def compare_3d_vectormaps(manalyser1, manalyser2, axes=None,
        illustrate=True, total_error=True, compact=False,
        animation=None, animation_type=None, animation_variable=None,
        optimal_ranges=None, pulsation_length=1, biphasic=False,
        kwargs1={}, kwargs2={}, kwargsD={}, **kwargs):
    '''
    Calls get 3d vectors for both analysers.
    Arrow rotation option only affects manalyser2
   
    Note! If total_error is true, sets attributes pupil_compare_errors
        and pupil_compare_rotations to the last ax in axes

    manalyser1,manalyser2 : objects
        Analyser objects
    axes : list of objects
        List of Matplotlib Axes objects. Expected base length == 3 which
        is modified by options orientation, total_error and compact.
    
    illustrate : bool
        Wheter to plot the illustrative plot. Increases the axes requirement by 1
    total_error: bool
        Whether to plot the total error plot Increases the axes requirement by 1
    compact : bool
        Join vectorplots in one. Decreases axes requirement by 1

    animation : list
        For total error x-axis limits
    kwargs1,kwargs2 : dict
        List of keyword arguments to pass to `plot_3d_vectormap`
    kwargsD : dict
        List of keywords arguments to pass to `plot_3d_differencemap`
    
    Returns [axes]
    '''


    optimal=False

    if axes is None:
        fig = plt.figure(figsize=(DEFAULT_FIGSIZE[0]*2,DEFAULT_FIGSIZE[1]*2))
        axes = []

        N_plots = 3
        
        if compact:
            N_plots -= 1 
        if total_error:
            N_plots += 1
        if illustrate:
            N_plots += 1

        n_rows = 1
        n_cols = N_plots

        for i_plot in range(N_plots):
            axes.append(fig.add_subplot(n_rows, n_cols, i_plot+1, projection='3d'))



    kwargs1 = kwargs.copy()
    kwargs2 = kwargs.copy()
    
    if animation_type == 'rotate_arrows':
        kwargs2['arrow_rotations'] = [animation_variable]
        kwargsD['colorbar_text_positions'] = [[0.5,1.03,'center', 'bottom'],
                [1.1,0.5,'left', 'center'],
                [0.5,-0.03,'center', 'top']]
        
        if manalyser1.__class__.__name__ == 'FAnalyser':
            manalyser1.constant_points = True

    elif animation_type in ['pitch_rot', 'roll_rot', 'yaw_rot']:
        kwargs2[animation_type] = animation_variable
        kwargsD['colinear'] = False
    elif animation_type == 'rotate_plot':
        kwargs1['elev'] = animation_variable[0]
        kwargs1['azim'] = animation_variable[1]
        kwargs2['elev'] = animation_variable[0]
        kwargs2['azim'] = animation_variable[1]

    # set 10 deg pitch for flow
    for manalyser in [manalyser1, manalyser2]:
        if manalyser.manalysers[0].__class__.__name__ == 'FAnalyser' and animation_type != 'pitch_rot':
            if manalyser == manalyser1:
                kwargs1['pitch_rot'] = 10
            if manalyser == manalyser2:
                kwargs2['pitch_rot'] = 10
            
            manalyser.pitch_rot = 10

    if manalyser2.__class__.__name__ == 'MAverage' and manalyser2.manalysers[0].__class__.__name__ == 'OAnalyser':
        kwargs2['arrows'] = False
    
    iax = 0
    plot_3d_vectormap(manalyser1, animation_type=animation_type, ax=axes[iax], **kwargs1)
    
    if not compact:
        iax += 1
    plot_3d_vectormap(manalyser2, animation_type=animation_type, ax=axes[iax], **kwargs2)
    

    if biphasic:
        # Difference with the slow phase
        iax += 1
        kwargsDr = kwargsD.copy()
        kwargsDr['colorbar'] = False
        daxr, reverse_errors = plot_3d_differencemap(manalyser1, manalyser2,
                ax=axes[iax], reverse_errors=True, **kwargsDr, **kwargs2)
    
    
    iax += 1
    dax, errors = plot_3d_differencemap(manalyser1, manalyser2,
            ax=axes[iax], **kwargsD, **kwargs2)
    
    if illustrate:

        # Check if we are at the optimal
        if optimal_ranges:
            for optimal_range in optimal_ranges:
                if optimal_range[0] < animation_variable < optimal_range[1]:
                    optimal=True
                    continue
        
        iax += 1
        ax = axes[iax]

        if animation_type == 'rotate_arrows':
            
            upscale = 4
            image = matplotlib.image.imread(os.path.join(CODE_ROOTDIR, 'images', 'dpp.tif'))
            image = PIL.Image.fromarray(image)
            ow,oh = image.size
            image = image.resize((int(ow*upscale), int(oh*upscale)), PIL.Image.NEAREST)
            image = np.array(image)

            # Vector p0,rp1 to point the current axis rotation
            R6R3line = 40
            rot = -math.radians( R6R3line + animation_variable ) 
            p0 = [int(image.shape[0]/2), int(image.shape[1]/2)]
            p1 = np.array([p0[0],0])/2
            rp1 = np.array([p1[0]*math.cos(rot)-p1[1]*math.sin(rot), p1[0]*math.sin(rot)+p1[1]*math.cos(rot)])
            
            # Optimal
            orot = -math.radians( R6R3line + np.mean(optimal_ranges[0][0:2]))
            orp1 = np.array([p1[0]*math.cos(orot)-p1[1]*math.sin(orot), p1[0]*math.sin(orot)+p1[1]*math.cos(orot)])
            
            # Make image pulsate
            sx, sy = (0,0)
            r= (0,0)
            if manalyser1.manalysers[0].__class__.__name__ == 'MAnalyser':
                r = image.shape
                r = [int(pr) for pr in [r[0]/20, r[1]/20, r[0]-r[0]/10, r[1]-r[1]/10]]

                # FIXME 0.6 is the low value of the pulsation
                sx = int(upscale * (orp1[0]) * (pulsation_length-0.8) / 10)
                sy = int(upscale * (orp1[1]) * (pulsation_length-0.8) / 10)
                
                #if not optimal:
                #    sx = 0
                #    sy = 0

                print('Animation pulsataion sx {} sy {}, imshape {}'.format(sx,sy, image.shape))
        
                #image[r[1]+sy:r[1]+r[3]+sy, r[0]+sx:r[0]+r[2]+sx] = image[r[1]:r[1]+r[3], r[0]:r[0]+r[2]]
                image = image[r[1]-sy:r[1]+r[3]-sy, r[0]-sx:r[0]+r[2]-sx]
            ax.imshow(image, cmap='gray')
           
            # R3-R6 dotted white line
            if manalyser1.manalysers[0].__class__.__name__ == 'FAnalyser':
                rot36 = -math.radians( R6R3line )
                rp1_36 = np.array([p1[0]*math.cos(rot36)-p1[1]*math.sin(rot36), p1[0]*math.sin(rot36)+p1[1]*math.cos(rot36)])
                ax.axline((p0[0]-r[0], p0[1]-r[1]), (p0[0]+rp1_36[0]-r[0], p0[1]+rp1_36[1]-r[1]), ls='--', color='white', lw=0.5)

            ax.axline((p0[0]-r[0], p0[1]-r[1]), (p0[0]+rp1[0]-r[0], p0[1]+rp1[1]-r[1]), color=REPEAT_COLORS[0])
            
            # Rhabdomere locations, dpp.tiff specific
            rhabdomere_locs = [(x*upscale+sx-r[0],y*upscale+sy-r[1]) for x,y in [(74,60),(68,79),(58,101),(80,94),(96,87),(100,66),(85,74)]]
            for i_rhabdomere, loc in enumerate(rhabdomere_locs):
                ax.text(*loc, 'R'+str(i_rhabdomere+1), color=(0.2,0.2,0.2), ha='center', va='center', fontsize=10)
            

        elif animation_type == 'pitch_rot':
            
            image = matplotlib.image.imread(os.path.join(CODE_ROOTDIR, 'images', 'from_mikko_annotated.png'))
            ax.imshow(rotate(image, animation_variable, mode='nearest', reshape=False)) 
            plot_2d_opticflow(ax, 'side')

        elif animation_type == 'yaw_rot':
            image = matplotlib.image.imread(os.path.join(CODE_ROOTDIR, 'images', 'rotation_yaw.png'))
            ax.imshow(rotate(image, animation_variable, mode='nearest', reshape=False))
            plot_2d_opticflow(ax, 'side')

        elif animation_type == 'roll_rot':
            image = matplotlib.image.imread(os.path.join(CODE_ROOTDIR, 'images', 'rotation_roll.png'))
            ax.imshow(rotate(image, animation_variable, mode='nearest', reshape=False))
            plot_2d_opticflow(ax, 'outofplane')


        if optimal_ranges:
            for optimal_range in optimal_ranges:
                if optimal_range[0] < animation_variable < optimal_range[1]:
                    rect = matplotlib.patches.Rectangle((0,0), 1, 1, transform=ax.transAxes, fill=False,
                            color='yellow', linewidth=8)
                    
                    ax.add_patch(rect)
                    ax.text(0.5, 0.9, optimal_range[2], ha='center', va='top', color='gold', transform=ax.transAxes, fontsize=12)
                    optimal=True
                    continue
   
        if manalyser1.manalysers[0].__class__.__name__ == 'FAnalyser' and manalyser2.manalysers[0].__class__.__name__ == 'OAnalyser':
            

            if getattr(axes[0], 'extra_illustrate_ax', None) is None:
                
                tmp_ax = axes[0].figure.add_subplot(3,4,8)
                tmp_ax.set_axis_off()
                cbox = tmp_ax.get_position()
                w = abs(cbox.x1 - cbox.x0)
                cbox.x0 += 0.25*w
                cbox.x1 += 0.25*w
                axes[0].extra_illustrate_ax = axes[0].figure.add_axes(cbox)
                axes[0].extra_illustrate_ax.set_frame_on(False)
                axes[0].extra_illustrate_ax.set_axis_off()
            else:
                axes[0].extra_illustrate_ax.clear()
                axes[0].extra_illustrate_ax.set_axis_off()
                axes[0].extra_illustrate_ax.set_frame_on(False)

            image = matplotlib.image.imread(os.path.join(CODE_ROOTDIR, 'images', 'from_mikko_annotated.png'))
            axes[0].extra_illustrate_ax.imshow(rotate(image, manalyser1.pitch_rot, mode='nearest', reshape=False))

            rect = matplotlib.patches.Rectangle((0.9+0.05,0), 0.02, 1, transform=axes[0].extra_illustrate_ax.transAxes, fill=True,
                    color='yellow', linewidth=1)
            
            axes[0].extra_illustrate_ax.add_patch(rect)
            # Optic flow arrows
            arrows = [np.array((1.2,ik))*len(image) for ik in np.arange(0.1,0.91,0.1)]
            for x, y in arrows:
                axes[0].extra_illustrate_ax.arrow(x, y, -0.1*len(image)*pulsation_length/2., 0, width=0.01*len(image), color='darkviolet')
        

    if total_error:
        iax += 1

    

        ax = axes[iax]
        if getattr(ax, 'pupil_compare_errors', None) is None:
            ax.pupil_compare_errors = []
            ax.pupil_compare_rotations = []

        ax.pupil_compare_errors.append(np.mean(errors))
        ax.pupil_compare_rotations.append( animation_variable )

        ax.plot( ax.pupil_compare_rotations, 1-np.array(ax.pupil_compare_errors), color='black',
                label='Fast phase')
        ax.scatter( ax.pupil_compare_rotations[-1], 1-ax.pupil_compare_errors[-1], color='black' )
       

        print('Minimum and maximum errors so far: {} (min, at angle {}), {} (max, at angle {})'.format(
            np.min(ax.pupil_compare_errors), ax.pupil_compare_rotations[np.argmin(ax.pupil_compare_errors)],
            np.max(ax.pupil_compare_errors), ax.pupil_compare_rotations[np.argmax(ax.pupil_compare_errors)]))

        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        
        ax.set_xlabel('Degrees')
        ax.set_ylabel('Mean error')

        if animation is not None:
            ax.set_xlim(np.min(animation), np.max(animation))
            ax.set_ylim(0,1)
            ax.set_yticks([0, 0.5, 1])
        
        if optimal:
            formatting = '{:.1f}'
        else:
            formatting = '{:.0f}'

        if animation_type == 'rotate_arrows':
            text = 'Rotation from R3-R6 line\n{} degrees'
        elif animation_type in ['pitch_rot', 'yaw_rot', 'roll_rot']:
            text = 'Head tilt {} degrees'
        else:
            text = 'Animation variable {}'
        
        if animation_variable is not None:
            text = text.format(formatting).format(float(animation_variable))
            ax.text(0.1, 1, text, transform=ax.transAxes, va='bottom', ha='left',fontsize=12)
        
        if np.min(animation) < -100 and np.max(animation) > 100:
            ax.set_xticks([-90,0,90])
            ax.set_xticklabels(['-90$^\circ$', '0$^\circ$','90$^\circ$'])   
        else:
            ax.set_xticks([-45, 0, 45])
            ax.set_xticklabels(['-45$^\circ$', '0$^\circ$','45$^\circ$'])   
        
        if biphasic:
            if getattr(ax, 'pupil_compare_reverse_errors', None) is None:
                ax.pupil_compare_reverse_errors = []

            ax.pupil_compare_reverse_errors.append(np.mean(reverse_errors))

            ax.plot( ax.pupil_compare_rotations, 1-np.array(ax.pupil_compare_reverse_errors), color='gray',
                    label='Slower phase')
            ax.scatter( ax.pupil_compare_rotations[-1], 1-ax.pupil_compare_reverse_errors[-1], color='gray' )
    
            ax.legend(loc=(0.39,1.2))


    return [axes]



def compare_3d_vectormaps_compact(*args, **kwargs):
    '''
    Wrapper for compare_3d_vectormaps but
        compact=True, total_error=False, illustrate=False
    '''
    return compare_3d_vectormaps(*args, compact=True, total_error=False, illustrate=False, **kwargs)



def compare_3d_vectormaps_manyviews(*args, axes=None,
        column_titles=['Microsaccades', 'Rhabdomere orientation', 'Difference', 'Mean microsaccade'],
        row_titles=['Dorsal\nview', 'Anterior\nview', 'Ventral\nview'],
        **kwargs):
    '''
    Just with different views rendered
    
    First axes gets attributes .orientation_ax and .error_ax
    '''
    

    views = [[50,90], [0,90], [-50,90]]
    rows = len(views)
    cols = 4
    
    biphasic = False
    if kwargs.get('animation_type', None) in ['pitch_rot', 'yaw_rot', 'roll_rot']:
        biphasic = True
        cols += 1
        column_titles.insert(3, 'Difference2')
    
        if kwargs.get('animation_type', None) in ['pitch_rot', 'yaw_rot', 'roll_rot']:
            column_titles[2] = 'Difference\n with slower phase'
            column_titles[3] = 'Difference\n with fast phase'
            column_titles[-1] = ''

        plt.subplots_adjust(left=0.05, bottom=0.04, right=0.9, top=0.94, wspace=0.05, hspace=0.05)
    else:
        plt.subplots_adjust(left=0.1, bottom=0.04, right=0.9, top=0.95, wspace=0.05, hspace=0.05)

    if axes is None:
        fig = plt.figure(figsize=DEFAULT_FIGSIZE,dpi=300)
        axes = []
        

        for i_view in range(rows):
            for column in range(cols-1):
                axes.append(fig.add_subplot(rows,cols,column+1+i_view*cols, projection='3d'))
        
        if getattr(kwargs, 'illustrate_ax', None) in [True, None]:
            # FIXME Very hacky way to move the subplot right. For some reason
            # when moved this way the plot also gets smaller?
            axes[0].illustrate_ax = fig.add_subplot(rows,cols,cols)
            cbox = axes[0].illustrate_ax.get_position()
            w = abs(cbox.x1 - cbox.x0)
            h = abs(cbox.y1 - cbox.y0)
            cbox.x0 -= w/8
            cbox.x1 += w / 3.3 +w/8
            cbox.y1 += h / 3.3
            
            if kwargs.get('animation_type', None) == 'pitch_rot':
                w = abs(cbox.x1 - cbox.x0)
                h = abs(cbox.y1 - cbox.y0)
                cbox.x0 -= w/5
                cbox.x1 += w/5
                cbox.y0 -= w/5
                cbox.y1 += w/5

            axes[0].illustrate_ax.set_position(cbox)
            axes[0].illustrate_ax.cbox = cbox

        if getattr(kwargs, 'total_error', None) in [True, None]:
            ax = fig.add_subplot(rows,cols,3*cols)
            ax_pos = ax.get_position()
            ax_pos = [ax_pos.x0+0.02, ax_pos.y0-0.04, ax_pos.width+0.022, ax_pos.height+0.02]
            ax.remove()
            ax = fig.add_axes(ax_pos)
            axes[0].error_ax = ax

        tmp_ax = fig.add_subplot(rows, cols, 2*cols)
        tmp_ax.set_axis_off()
        cbox = tmp_ax.get_position()
        
        cbox.x1 -= abs(cbox.x1 - cbox.x0)/1.1
        w = abs(cbox.x1 - cbox.x0)
        cbox.x0 -= 2*w
        cbox.x1 -= 2*w
        axes[0].colorbar_ax = ax.figure.add_axes(cbox)
    
    # Clear axes that are attributes of the axes[0]; These won't
    # otherwise get cleared for the animation/video
    
    if getattr(axes[0], 'error_ax', None) is not None:
        axes[0].error_ax.clear()
    
    # Set custom column titles
    for i_manalyser in range(2):
        manalyser = args[i_manalyser]
        if manalyser.manalysers[0].__class__.__name__ == 'FAnalyser' or manalyser.__class__.__name__ == 'FAnalyser':
            if '\n' in ''.join(column_titles):
                column_titles[i_manalyser] = 'Optic flow\n'
            else:
                column_titles[i_manalyser] = 'Optic flow'

        if manalyser.manalysers[0].__class__.__name__ == 'MAnalyser' and manalyser.manalysers[0].receptive_fields == True:
            column_titles[i_manalyser] = 'Biphasic receptive field\nmovement directions'


    if args[0].manalysers[0].__class__.__name__ == 'FAnalyser':
        column_titles[cols-1] = 'Mean optic flow axis'

    if getattr(axes[0], 'illustrate_ax', None) is not None:
        axes[0].illustrate_ax.clear()
        axes[0].illustrate_ax.set_title(column_titles[-1], color=REPEAT_COLORS[0])
        #axes[0].illustrate_ax.text(0.5,1, column_titles[-1], transform=axes[0].illustrate_ax.transAxes, ha='center', va='bottom')        
        axes[0].illustrate_ax.set_frame_on(False)
        axes[0].illustrate_ax.set_axis_off()

    # Add column titles
    for title, ax in zip(column_titles[:-1], axes[0:cols-1]):
        ax.set_title(title)
    
    # Add row titles for the views
    for title, ax in zip(row_titles, axes[::cols-1]):
        if biphasic:
            ax.text2D(-0.1, 0.5, title.replace('\n', ' '), transform=ax.transAxes, va='center', ha='center', rotation=90)
        else:
            ax.text2D(-0.375, 0.5, title, transform=ax.transAxes, va='center')

    for ax in axes:
        ax.set_axis_off()
    
    naxes = cols -1

    for i in range(3):
        viewargs = copy.deepcopy(kwargs)
        viewargs['elev'] = views[i][0]
        viewargs['azim'] = views[i][1]
        
        if i == 0:
            compare_3d_vectormaps(axes=axes[i*naxes:(i+1)*naxes]+[axes[0].illustrate_ax, axes[0].error_ax],
                    biphasic=biphasic,
                    kwargsD={'colorbar': True, 'colorbar_ax': axes[0].colorbar_ax},
                    illustrate=True, total_error=True,
                    *args, **viewargs)
        else:
            compare_3d_vectormaps(axes=axes[i*naxes:(i+1)*naxes]+[axes[0].illustrate_ax, axes[0].error_ax],
                    biphasic=biphasic, illustrate=False, total_error=False,
                    kwargsD={'colorbar': False},
                    *args, **viewargs)
    
    for ax in axes:
        ax.dist = 6

    axes[0].illustrate_ax.set_position(axes[0].illustrate_ax.cbox)
    return [axes]
