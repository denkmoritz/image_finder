import matplotlib.pyplot as plt
import numpy as np
import math
import random


def plot_simple_slice(inner_buffer=8, outer_buffer=12):
    # Random heading in degrees, where 0° is north and direction is clockwise
    heading_deg = random.uniform(0, 45)
    heading_rad = math.radians(heading_deg)

    # Create polar grid for ring (annulus)
    theta = np.linspace(0, 2 * np.pi, 300)
    outer_x = outer_buffer * np.sin(theta)
    outer_y = outer_buffer * np.cos(theta)
    inner_x = inner_buffer * np.sin(theta)
    inner_y = inner_buffer * np.cos(theta)

    # Create the corridor polygon (rectangle)
    corridor_length = outer_buffer * 2
    corridor_width = inner_buffer * 2

    # Four corners of the corridor in unrotated space
    cx = np.array([-corridor_width / 2, corridor_width / 2, corridor_width / 2, -corridor_width / 2])
    cy = np.array([-corridor_length / 2, -corridor_length / 2, corridor_length / 2, corridor_length / 2])

    # Rotate corridor to match heading
    rot_x = cx * math.cos(-heading_rad) - cy * math.sin(-heading_rad)
    rot_y = cx * math.sin(-heading_rad) + cy * math.cos(-heading_rad)

    # Generate a random point in the ring excluding corridor
    def random_point_in_slice():
        for _ in range(1000):
            r = random.uniform(inner_buffer, outer_buffer)
            angle = random.uniform(0, 2 * np.pi)
            x = r * math.sin(angle)
            y = r * math.cos(angle)

            # Rotate point back to corridor-aligned space
            rx = x * math.cos(heading_rad) - y * math.sin(heading_rad)
            ry = x * math.sin(heading_rad) + y * math.cos(heading_rad)

            if not (-corridor_width / 2 <= rx <= corridor_width / 2 and -corridor_length / 2 <= ry <= corridor_length / 2):
                return x, y
        return None, None

    px, py = random_point_in_slice()

    # ---- Plot ----
    fig, ax = plt.subplots()
    ax.plot(outer_x, outer_y, color='black', linestyle='--')
    ax.plot(inner_x, inner_y, color='black', linestyle='--')
    ax.annotate(f"{inner_buffer} m", xy=(inner_buffer, 0), xytext=(inner_buffer + 2, 1),
                arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.annotate(f"{outer_buffer} m", xy=(outer_buffer, 0), xytext=(outer_buffer + 2, 1),
                arrowprops=dict(arrowstyle="->"), fontsize=9)

    ax.fill(rot_x, rot_y, facecolor='none', edgecolor='black', hatch='//', linestyle='--', linewidth=1)

    if px is not None:
        ax.scatter(px, py, color='red', label='Possible Point in Slice')
    ax.scatter(0, 0, color='black', label='Center')

    ax.set_aspect('equal')
    plt.tick_params(axis='x', labelbottom=False)
    plt.tick_params(axis='y', labelleft=False)

    ax.set_title(f'Slice Zone (Heading {heading_deg:.1f}°)')
    ax.legend(loc='upper right')
    plt.tight_layout()
    plt.show()


if __name__ == '__main__':
    plot_simple_slice(inner_buffer=8, outer_buffer=12)