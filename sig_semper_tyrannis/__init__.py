import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from turtlesim.msg import Pose
from turtlesim.srv import SetPen

"""
Cara Kerja Stroke:
    - Stroke berarti garis / kumpulan garis
    - Setiap list dalam (inner list) merupakan 1 bentuk
    - Setiap dictionary dalam inner list merupakan 1 titik koord
    - Dilakukan pen_down untuk bergerak dari titik ke titik pada 1 bentuk
    - Setiap berpindah list berarti pen_up (tidak menggambar namun berubah posisi)
"""

STROKES = [
    # SIG SEMPER TYRANNIS
    # SIG
    [(1.7, 2.6), (1.1, 2.6), (1.1, 2.25), (1.7, 2.25), (1.7, 1.9), (1.1, 1.9)],
    [(2.3, 2.6), (2.3, 1.9)],
    [(3.5, 2.6), (2.9, 2.6), (2.9, 1.9), (3.5, 1.9), (3.5, 2.25), (3.2, 2.25)],
    # SEMPER
    [(5.3, 2.6), (4.7, 2.6), (4.7, 2.25), (5.3, 2.25), (5.3, 1.9), (4.7, 1.9)],
    # E
    [(6.2, 2.6), (5.6, 2.6), (5.6, 1.9), (6.2, 1.9)],
    [(5.6, 2.25), (6.1, 2.25)],
    # M
    [(6.5, 1.9), (6.5, 2.6), (6.8, 2.2), (7.1, 2.6), (7.1, 1.9)],
    # P
    [(7.4, 1.9), (7.4, 2.6), (8.0, 2.6), (8.0, 2.25), (7.4, 2.25)],
    # E
    [(8.9, 2.6), (8.3, 2.6), (8.3, 1.9), (8.9, 1.9)],
    [(8.3, 2.25), (8.8, 2.25)],
    # R
    [(9.2, 1.9), (9.2, 2.6), (9.8, 2.6), (9.8, 2.25), (9.2, 2.25), (9.8, 1.9)],
    # TYRANNIS
    # T
    [(2.0, 1.3), (2.6, 1.3), (2.3, 1.3), (2.3, 0.6)],
    # Y
    [(2.9, 1.3), (3.2, 0.95), (3.5, 1.3), (3.2, 0.95), (3.2, 0.6)],
    # R
    [(3.8, 0.6), (3.8, 1.3), (4.4, 1.3), (4.4, 0.95), (3.8, 0.95), (4.4, 0.6)],
    # A
    [(4.7, 0.6), (5.0, 1.3), (5.3, 0.6), (5.17, 0.9), (4.83, 0.9)],
    # N
    [(5.6, 0.6), (5.6, 1.3), (6.2, 0.6), (6.2, 1.3)],
    # N
    [(6.5, 0.6), (6.5, 1.3), (7.1, 0.6), (7.1, 1.3)],
    # I
    [(7.7, 1.3), (7.7, 0.6)],
    # S
    [(8.9, 1.3), (8.3, 1.3), (8.3, 0.95), (8.9, 0.95), (8.9, 0.6), (8.3, 0.6)],
    # Mereka yang "diatas"
    # Kepalanya dasi
    [(4.8, 6.8), (4.8, 6.0), (5.5, 5.5), (6.2, 6.0), (6.2, 6.8)],
    # # Kepala
    [(3.5, 9.0), (7.5, 9.0), (5.5, 6.0), (3.5, 9.0)],
    # Telinga kanan
    [(1.9, 10.8), (4.0, 10.0), (3.5, 9.0), (1.9, 9.0), (1.9, 10.8)],
    # Telinga kiri
    [(9.0, 10.8), (6.9, 10.0), (7.4, 9.0), (9.0, 9.0), (9.0, 10.8)],
    # Mata kanan
    [(4.5, 7.7), (5.0, 8.0), (5.4, 7.4), (4.5, 7.7)],
    # Mata kiri
    [(6.5, 7.7), (5.9, 8.0), (5.5, 7.4), (6.5, 7.7)],
    # Badan
    [(4.8, 7.0), (2.9, 3.0), (7.9, 3.0), (6.2, 7.0)],
    # Badannya dasi
    [(5.4, 5.5), (5.0, 4.0), (5.4, 3.0), (5.9, 4.0), (5.4, 5.5)],
    # SIG SEMPER TYRANNIS!
]


def wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))

# Menjaga kecepatan turtle dalam batas ttntu
# Kalau ga pakai clamping turtle akan berhenti di tengah jalan dan lanjut
def clamp(val, minval, maxval):
    return max(minval, min(maxval, val))


class TurtleArt(Node):
    def __init__(self):
        super().__init__("draw_sig_semper")
        self.cmd_pub = self.create_publisher(Twist, "/turtle1/cmd_vel", 10)
        self.create_subscription(Pose, "/turtle1/pose", self.on_pose, 10)
        self.pen_client = self.create_client(SetPen, "/turtle1/set_pen")

        self.pose = None
        self.steps = []  # langkah disimpan disini (x, y, pen_down)
        self.cwpidx = 0  # index wp saat ini
        self.pen_ready = False
        self.state = "ROTATE"  # ROTATE atau MOVE
        self.pen_on = None  # atur pena menyentuh / tidak
        self.finished = False

        for stroke in STROKES:
            self.add_stroke(stroke)

        self.get_logger().info(f"Total ada {len(self.steps)} titik")
        self.create_timer(0.01, self.control)  # 100 Hz

    def on_pose(self, msg):
        self.pose = msg

    def add_stroke(self, points):
        # Buat turtle bergerak tanpa menggambar ke waypoint pertama dari setiap bentuk
        x, y = points[0]
        self.steps.append((x, y, False))

        # Selain waypoint pertama dari setiap bentuk, pen down utk menggambar
        for x, y in points[1:]:
            self.steps.append((x, y, True))  # draw to here

    def stop(self):
        self.cmd_pub.publish(Twist())

    def control(self):
        if self.pose is None:
            return

        # Program selesai ketika index wp saat sdh sama / lebih dari panjang step
        if self.cwpidx >= len(self.steps):
            if not self.finished:
                self.stop()
                self.finished = True
                self.get_logger().info("Done!")
            return

        target_x, target_y, pen = self.steps[self.cwpidx]

        # Pengaturan pena
        if not self.pen_ready:
            if not self.pen_client.service_is_ready():
                return
            if pen != self.pen_on:
                req = SetPen.Request()
                req.r, req.g, req.b = 255, 255, 255
                req.width = 3
                req.off = 0 if pen else 1
                self.pen_client.call_async(req)

                self.pen_on = pen

            self.pen_ready = True
            self.state = "ROTATE"

        # Menghitung selisih jarak antara koordinat target dan posisi turtle di sumbu
        dist_x = target_x - self.pose.x
        dist_y = target_y - self.pose.y
        dist = math.hypot(dist_x, dist_y)

        # Jika ada ketidakakuratan dibawah 0.02 maka dimaklumkan, dan pindah ke index way point berikutnya
        if dist < 0.02:
            self.stop()
            self.cwpidx += 1
            self.pen_ready = False
            return

        # delta_angle; atau sbrp banyak nilai/perubahan agar turtle menghadap target
        del_angle = wrap(math.atan2(dist_y, dist_x) - self.pose.theta)
        cmd = Twist()

        if self.state == "ROTATE":
            if abs(del_angle) < 0.02: # jika kurang dari 0.02 (nilai toleransi) mulai maju
                self.state = "MOVE"
            else:
                w = clamp(6.0 * abs(del_angle), 0.3, 6.0)
                cmd.angular.z = math.copysign(w, del_angle) # +err maka target di kiri, -err maka target di kanan

        if self.state == "MOVE":
            cmd.linear.x = clamp(3.0 * dist, 0.2, 3.0)
            if dist > 0.1:
                cmd.angular.z = clamp(6.0 * del_angle, -3.0, 3.0)  # keep line straight
            if abs(del_angle) > 0.4: 
                self.state = "ROTATE"

        self.cmd_pub.publish(cmd)


def main():
    rclpy.init()
    node = TurtleArt()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
