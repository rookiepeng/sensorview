import numpy as np

import plotly.io as pio


def get_scatter3d_layout(
    x_range,
    y_range,
    z_range=[-20, 20],
    height=650,
    title=None,
    margin=dict(l=0, r=0, b=0, t=20),
    template='plotly',
    image=None
):
    scale = np.min([x_range[1]-x_range[0], y_range[1] -
                    y_range[0], z_range[1]-z_range[0]])

    if image is not None:
        img_dict = [dict(
            source=image,
            xref="x domain",
            yref="y domain",
            x=0,
            y=1,
            xanchor="left",
            yanchor="top",
            sizex=0.3,
            sizey=0.3,
        )]
    else:
        img_dict = None

    return dict(
        title=title,
        # template=pio.templates['plotly_dark'],
        template=pio.templates[template],
        height=height,
        scene=dict(xaxis=dict(range=x_range,
                              title='Lateral (m)',
                              autorange=False),
                   yaxis=dict(range=y_range,
                              title='Longitudinal (m)', autorange=False),
                   zaxis=dict(range=z_range,
                              title='Height (m)', autorange=False),
                   aspectmode='manual',
                   aspectratio=dict(x=(x_range[1]-x_range[0])/scale,
                                    y=(y_range[1]-y_range[0])/scale,
                                    z=(z_range[1]-z_range[0])/scale),
                   ),
        margin=margin,
        legend=dict(x=0, y=0),
        images=img_dict,
        uirevision='no_change',
    )
