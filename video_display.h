#pragma once
//VGA
#define RAW_IMAGE_SIZE_VGA_PIX (640 * 480)
#define RAW_IMAGE_SIZE_VGA_RAW (640 * 480 * 2)
#define RAW_IMAGE_SIZE_VGA_RGB (640 * 480 * 3)
//720p
#define RAW_IMAGE_SIZE_720p_PIX (1280 * 720)
#define RAW_IMAGE_SIZE_720p_RAW (RAW_IMAGE_SIZE_720p_PIX* 2)
#define RAW_IMAGE_SIZE_720p_RGB (RAW_IMAGE_SIZE_720p_PIX * 3)
//5MP
#define RAW_IMAGE_SIZE_5MP_PIX (2592 * 1944)
#define RAW_IMAGE_SIZE_5MP_RAW (RAW_IMAGE_SIZE_720p_PIX * 2)
#define RAW_IMAGE_SIZE_5MP_RGB (RAW_IMAGE_SIZE_720p_RGB * 3)
#include <cstdint>
#include <cstring>
#include <cstdio>
#include "util_image.h"
#include "opencv2/opencv.hpp"
#include "SerialPort.h"
#include "leopard_cam.h"
#include <array>
#include <fstream>
#include <iostream>
#include <queue> 
#include <bitset>
#include "rapidjson/document.h"
#include "rapidjson/writer.h"
#include "rapidjson/stringbuffer.h"
#include <chrono>
#include "zmq.hpp"
#include <vector>

#define MAX_VIDEO_FRAMES 600
int num_frames = MAX_VIDEO_FRAMES;
double fps = 0;
std::chrono::time_point<std::chrono::high_resolution_clock> chrono_times[MAX_VIDEO_FRAMES];
auto chrono_start_time = std::chrono::high_resolution_clock::now();

unsigned long video_bytes = 0;
float scale = 1.0;
int video_save = 0;
struct tm time_thresh;

double start_sf = 1.065;
std::string pic_dir;
using namespace std;
using namespace cv;
using namespace rapidjson;
#define BAUDRATE 19200
//string prefix = "C:/Users/davidsachs/Documents/themachine/";
string prefix = "C:/dev/themachine/";
//string prefix = "F:/themachine/";
string python = "C:/Users/David Sachs/.pyenv/pyenv-win/shims/python";
//string python = "C:/Users/davidsachs/anaconda3/python";
//string python = "C:/Users/themachine_desktop/anaconda3/python";
//char *port_name = "\\\\.\\COM4";
char *port_name = "\\\\.\\COM4";
//char *co2_port = "\\\\.\\COM3";
//char* dac_port = "\\\\.\\COM5";
float co2 = 0;
auto video_in = std::make_unique<video_in_base>();
char incomingData[MAX_DATA_LENGTH];
char co2Data[MAX_DATA_LENGTH];
int frame_count = 0;
int video_frame = 0;
bool recording_video = false;
bool taking_picture = false;
bool firsttime = true;
bool firstimage = true;
int exposure = 2;
SerialPort *arduino;
SerialPort* dacArduino;
//SerialPort co2_sensor(co2_port, 9600);
unsigned int serial_ptr = 0;
unsigned int read_serial_ptr = 0;
unsigned int co2_serial_ptr = 0;
unsigned int co2_read_serial_ptr = 0;
unsigned int hough_buffer_ind = 0;

// DLP sockets - may cause IO thread congestion if dlp.local is unreachable
zmq::context_t context(1);
zmq::socket_t socket_zmq(context, zmq::socket_type::push);
zmq::socket_t pull_socket(context, zmq::socket_type::pull);
zmq::socket_t data_socket(context, zmq::socket_type::pub);

// Image and command sockets get their own contexts so they're never
// starved by dlp.local reconnect attempts on the main context
zmq::context_t image_context(1);
zmq::socket_t image_socket(image_context, zmq::socket_type::pub);

zmq::context_t cmd_context(1);
zmq::socket_t cmd_socket(cmd_context, zmq::socket_type::pull);

#define HOUGH_CONF_IND_MAX 20

int hough_conf[HOUGH_CONF_IND_MAX] = { 0 };
int hough_conf_ind = 0;
int hough_conf_total = 0;
float start_yaw = 0;// -3.0 * CV_PI / 180.0f;//0
//bool logfile = false;
ofstream log_file(prefix+"log.txt", ios::app);
ofstream acc_file(prefix + "acclog.txt", ios::app);
std::string input_text = "";
Point laser = Point(698-150, 454+250);
cv::Mat prev_image, flow, image_debug, detected_edges, detected_edges_focus, detected_edges_tmp, contoured_edges, threshold_image;
double xintegral = 0, yintegral = 0;
double integralang = 0;
double flowmag = 0;
double flowang = 0;
unsigned long arduino_num = 0;
double xlaser = 0, ylaser = 0;
double xlaserint = 0, ylaserint = 0;
int lasermoving = 0;
//int lasermovingcount = 0;
double lasermag = 0;
double xlaserinc = 0;
double ylaserinc = 0;
double laserincmag = 5;
double laserang = 0;
double origlaserang = 0;
double chip_feedback_x = 0;
double chip_feedback_y = 0;
double fudge = 1.0;// 1.03;
double chip_pos_x = 0;
double chip_pos_y = 0;
int cond = 0;
bool center_fail = true;
int well_number = -1;
int chip_number = -1;
int focus_delay = 0;
string last_command = "";
string next_command = "";
string serial_command = "";
string last_serial_command = "";
int restart_mode[8] = { 0 };
long motor[8] = { 0 };
long prev_motor[8] = { 0 };
int button_mode = 100;
double double_click_time = 0;
int double_click_count = 0;
#define MOVE_MOTOR 0
#define MOVE_REF 1
#define MOVE_FEEDBACK 2

#define IMAGE_MICRO 0
#define IMAGE_OPENCV 1
#define IMAGE_MICRO_OPENCV 2
#define IMAGE_MICRO_PROJECTOR 3
#define IMAGE_ALIGN 4

float proj_targ_x = 0;
float proj_targ_y = 0;
float proj_targ_sx = 1.0f;
float proj_targ_sy = 1.0f;
float proj_targ_r = 0;

float proj_adj_x = 0;
float proj_adj_y = 0;
//float proj_adj_s = 1.0f;
float proj_adj_sx = 1.0f;
float proj_adj_sy = 1.0f;
float proj_adj_r = 0;
bool proj_done = false;
Mat image_sub;
Mat proj_sub;
bool update_proj = false;
int update_proj_illum = 0;

// Drag state for projector mask (used by both local mouse_callback and remote mouse events)
int drag_mode = 0;
int drag_start_x = 0;
int drag_start_y = 0;

float acc_sum[6] = { 0 };
int acc_count = 0;

unsigned long timedout = 0;
unsigned int image_attempts = 0;
int move_mode = MOVE_MOTOR;
int image_mode = IMAGE_MICRO;
bool image_send = true;
int motor_busy_mode = 0;
unsigned char motor_busy_num[8] = { 255, 255, 255, 255, 255, 255, 255, 255 };
unsigned char prev_motor_busy_num[8] = { 255, 255, 255, 255, 255, 255, 255, 255 };
bool automating = false;
double latency_time = 0;
bool latency = false;
double prev_automate_time = 0;
double prev_motor_busy_time[8] = { 0 };
double prev_focus_time = 0;
double prev_lighting_time = 0;
double prev_button_time = 0;
double prev_hough_time = 0;
long automate_delay = 0;
string auto_delay_type = "SLEEP0";
string auto_text = "";
bool motor_busy[8] = { false };
int automate_ind = 0;
std::vector<string> automate;
std::vector<double> centerx(7,0);
std::vector<double> centery(7,0);
int center_count = 0;
unsigned long focus_levels[16] = { 0 };
unsigned long focus_edges[500] = { 0 };
float focus_line[500] = { 0 };
double focus_motor[500] = { 0 };
bool run_flow = false;

bool run_hough_circles = true;// true;
bool run_hough_lines = true;

bool run_contours = false;// true;
bool run_map = false;
bool run_focus = false;
int align_mode = 0;
bool run_lighting = false;
int lighting_mode = 0;
int focus_mode = 0;
double prev_focus_max = 0;
int lighting_type = 0;
double lighting_max[500] = { 0 };
double lighting_min[500] = { 0 };
int lighting_circles[500] = { 0 };
double lighting_mean[500] = { 0 };
double lighting_stddev[500] = { 0 };
int lighting_ind = 0;
string auto_file_num = "";
int run_center = 0;
bool running = false;
int focus_level = 0;
int lighting = 0;
int current_chip = 0;
double chip_offset_x[12] = { 0 };
double chip_offset_y[12] = { 0 };
double chip_offset_z[12] = { 0 };
double chip_yaw[12] = { 0 };
double chip_sf[12] = { 1.0 };

//float orientation = 0;// -90 * CV_PI / 180.0;
//float orientation =  -90 * CV_PI / 180.0;
//float orientations[12] = { 0 };// { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -90 * CV_PI / 180.0, 0 };
//float orientations[12] = { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -90 * CV_PI / 180.0, 0 };

#define TAB_LEFT 0*CV_PI/180.0
#define TAB_RIGHT 180*CV_PI/180.0
#define TAB_IN -90*CV_PI/180.0
#define TAB_OUT 90*CV_PI/180.0

float orientations[12] = { TAB_IN,TAB_IN,TAB_IN,
						TAB_IN, TAB_IN, TAB_IN,
						TAB_IN, TAB_IN, TAB_IN,
						TAB_IN, TAB_IN, TAB_IN };
//0: tab left
//-90: tab in
//+90: tab out
//180: tab right



//float orientations[12] = { -90 * CV_PI / 180.0 };// { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -90 * CV_PI / 180.0, 0 };
double camera_offset_x_init = 0;
double camera_offset_y_init = 0;
double camera_offset_z_init = 0;

double home_x = 0;
double home_y = 0;
double home_z = 0;
double home_obj = 0;
double camera_offset_x_driver = 0;
double camera_offset_y_driver = 0;
double camera_offset_z_driver = 0;
// Position tracking no longer needs wraparound handling -
// Arduino firmware now sends full 32-bit software-tracked positions
double camera_offset_x = 0;
double camera_offset_y = 0;
double camera_offset_z = 0;

double front_belt_home = 0;
double back_belt_home = 0;
double front_belt = 0;
double front_belt_driver = 0;
double front_belt_init = 0;
double back_belt = 0;
double back_belt_driver = 0;
double back_belt_init = 0;
#define NUM_OBJECTIVES 3
double objective_offset_driver = 0;
int objective = 0;           // index into objective_pos[] (0, 1, 2)
int objective_mag = 1;       // magnification for display (1, 4, 10)
double objective_offset_init = 0;
double objective_offset = 0;
const double objective_pos[3] = { -25, 0, 25 };
// Magnification-to-index mapping: GO1→0, GO4→1, GO10→2
const int obj_mags[3] = { 1, 4, 10 };

int mag_to_index(int mag) {
	for (int i = 0; i < NUM_OBJECTIVES; i++) {
		if (obj_mags[i] == mag) return i;
	}
	return 0;  // default to index 0
}



long small_stepper[30] = { 0 };
#define FRONT_ROCKER_HOLD 26
#define BACK_ROCKER_HOLD 29
#define Z_MOTOR 12
#define Z_MOTOR_STEPS 13
double front_rocker_angle = 0;
double back_rocker_angle = 0;
double front_rocker_noise = 0;
double back_rocker_noise = 0;
#define NOISE_MAX 10
double front_noise[NOISE_MAX];
double back_noise[NOISE_MAX];
double front_noise_max = 0;
double back_noise_max = 0;
int front_noise_ind = 0;
int back_noise_ind = 0;


unsigned long switches = 0;
long lightnum = -1;
unsigned int light = 0;
long light_a = 0;
long light_b = 0;
long light_c = 0;
//double focus = 0;
//double focus_init = 0;
int auto_count = 0;
bool paused = false;
int program_paused = 0;
Mat projector;
Mat proj_mask;
Mat proj_ref;
Mat proj_adj;
float proj_illum_time = 20;
string mask_file_name = "";
std::vector<cv::Mat> proj_video_frames;  // numbered mask frames for PROJV
bool proj_video_mode = false;            // true when a video sequence is loaded
int proj_video_index = -1;              // current frame being displayed (-1 = not running)
bool proj_video_sending = false;         // true while video sequence is actively sending
int proj_video_next_send = 0;           // index of next frame to send to Pi (always one ahead of display)
auto proj_video_deadline = std::chrono::high_resolution_clock::now();

Mat kernel = getStructuringElement(MORPH_RECT, Size(10, 10));

vector<Vec4f> detect_lines_lsd(const Mat& gray_img) {
	Ptr<LineSegmentDetector> lsd = createLineSegmentDetector(LSD_REFINE_STD);
	vector<Vec4f> lines;
	lsd->detect(gray_img, lines);
	return lines;
}

// Draw lines on image
Mat draw_lines(const Mat& image, const vector<Vec4f>& lines, Scalar color = Scalar(0, 255, 0)) {
	Mat img_lines = image.clone();
	for (const auto& ln : lines) {
		Point pt1(cvRound(ln[0]), cvRound(ln[1]));
		Point pt2(cvRound(ln[2]), cvRound(ln[3]));
		cv::line(img_lines, pt1, pt2, color, 1); // explicitly call cv::line
	}
	return img_lines;
}

void write_meta_file(String meta_file, bool frames=false) {
	StringBuffer s;
	Writer<StringBuffer> writer(s);

	writer.StartObject();               // Between StartObject()/EndObject(), 
	writer.Key("chip_number");                // output a key,
	writer.Double(current_chip);

	writer.Key("well_number");                // output a key,
	writer.Double(well_number);

	
	writer.Key("home_x");                // output a key,
	writer.Double(home_x);
	writer.Key("home_y");                // output a key,
	writer.Double(home_y);
	writer.Key("home_z");                // output a key,
	writer.Double(home_z);
	writer.Key("front_belt_home");                // output a key,
	writer.Double(front_belt_home);
	writer.Key("back_belt_home");                // output a key,
	writer.Double(back_belt_home);
	writer.Key("camera_offset_x_init");                // output a key,
	writer.Double(camera_offset_x_init);
	writer.Key("camera_offset_y_init");                // output a key,
	writer.Double(camera_offset_y_init);
	writer.Key("camera_offset_z_init");                // output a key,
	writer.Double(camera_offset_z_init);

	writer.Key("front_belt_init");                // output a key,
	writer.Double(front_belt_init);
	writer.Key("back_belt_init");                // output a key,
	writer.Double(back_belt_init);


	writer.Key("camera_offset_x");                // output a key,
	writer.Double(camera_offset_x);
	writer.Key("camera_offset_y");                // output a key,
	writer.Double(camera_offset_y);
	writer.Key("camera_offset_z");                // output a key,
	writer.Double(camera_offset_z);
	
	writer.Key("objective_offset_init");                // output a key,
	writer.Double(objective_offset_init);

	writer.Key("front_rocker_angle");
	writer.Double(front_rocker_angle);
	writer.Key("back_rocker_angle");
	writer.Double(back_rocker_angle);
	writer.Key("front_rocker_noise");
	writer.Double(front_rocker_noise);
	writer.Key("back_rocker_noise");
	writer.Double(back_rocker_noise);
	writer.Key("co2");
	writer.Double(co2);
	writer.Key("switches");
	writer.Double(switches);


	//writer.Key("focus");                // output a key,
	//writer.Double(focus);

	
	
	writer.Key("light_num");                // output a key,
	writer.Double(lightnum);
	writer.Key("light");                // output a key,
	writer.Double(light);

	writer.Key("light_a");                // output a key,
	writer.Double(light_a);

	writer.Key("light_b");                // output a key,
	writer.Double(light_b);

	writer.Key("light_c");                // output a key,
	writer.Double(light_c);


	writer.Key("exposure");                // output a key,
	writer.Double(exposure);

	if (frames) {
		writer.Key("Frames");                // output a key,
		writer.StartArray();
		for (int i = 0; i < num_frames; i++) {
			auto chrono_frame_time = (chrono_times[i] - chrono_start_time) / std::chrono::microseconds(1);
			writer.Int64(chrono_frame_time);
		}
		writer.EndArray();
	}	
	writer.EndObject();

	cout << s.GetString() << endl;
	std::ofstream out(meta_file);
	out << s.GetString();
	out.close();

}
void store() {
	StringBuffer s;
	Writer<StringBuffer> writer(s);

	writer.StartObject();               // Between StartObject()/EndObject(), 
	writer.Key("home_x");                // output a key,
	writer.Double(home_x);
	writer.Key("home_y");                // output a key,
	writer.Double(home_y);
	writer.Key("home_z");                // output a key,
	writer.Double(home_z);
	writer.Key("front_belt_home");                // output a key,
	writer.Double(front_belt_home);
	writer.Key("back_belt_home");                // output a key,
	writer.Double(back_belt_home);

	writer.Key("camera_offset_x_init");                // output a key,
	writer.Double(camera_offset_x);
	writer.Key("camera_offset_y_init");                // output a key,
	writer.Double(camera_offset_y);
	writer.Key("camera_offset_z_init");                // output a key,
	writer.Double(camera_offset_z);
	writer.Key("objective_offset_init");                // output a key,
	writer.Double(objective_offset);
	writer.Key("front_belt_init");                // output a key,
	writer.Double(front_belt_init);
	writer.Key("back_belt_init");                // output a key,
	writer.Double(back_belt_init);

	//writer.Key("camera_offset_x");                // output a key,
	//writer.Double(camera_offset_x);
	//writer.Key("camera_offset_y");                // output a key,
	//writer.Double(camera_offset_y);
	//writer.Key("camera_offset_z");                // output a key,
	//writer.Double(camera_offset_z);
	//writer.Key("focus");                // output a key,
	//writer.Double(focus);
	
	writer.Key("objective_mag");
	writer.Int(objective_mag);

	
	writer.Key("chip_offset_x");                // output a key,
	writer.StartArray();
	for (int i = 0; i < 12; i++) {
		writer.Double(chip_offset_x[i]);
	}
	writer.EndArray();

	writer.Key("chip_offset_y");                // output a key,
	writer.StartArray();
	for (int i = 0; i < 12; i++) {
		writer.Double(chip_offset_y[i]);
	}
	writer.EndArray();

	writer.Key("chip_offset_z");                // output a key,
	writer.StartArray();
	for (int i = 0; i < 12; i++) {
		writer.Double(chip_offset_z[i]);
	}
	writer.EndArray();

	writer.Key("proj_targ_x");
	writer.Double(proj_targ_x);
	writer.Key("proj_targ_y");
	writer.Double(proj_targ_y);
	writer.Key("proj_targ_sx");
	writer.Double(proj_targ_sx);
	writer.Key("proj_targ_sy");
	writer.Double(proj_targ_sy);

	writer.Key("proj_targ_r");
	writer.Double(proj_targ_r);
	writer.Key("proj_adj_x");
	writer.Double(proj_adj_x);
	writer.Key("proj_adj_y");
	writer.Double(proj_adj_y);
	writer.Key("proj_adj_sx");
	writer.Double(proj_adj_sx);
	writer.Key("proj_adj_sy");
	writer.Double(proj_adj_sy);
	writer.Key("proj_adj_r");
	writer.Double(proj_adj_r);

	writer.EndObject();

	cout << s.GetString() << endl;

	std::ofstream out(prefix + "settings.txt");
	out << s.GetString();
	out.close();
}
void load() {
	//for (int i = 0; i < 12; i++) {
	//	orientations[i] = -90 * CV_PI / 180.0;
	//	//orientations[i] = 0;
	//}
	//orientations[10] = 0;
	std::ifstream t(prefix + "settings.txt");
	std::stringstream stringbuffer;
	stringbuffer << t.rdbuf();
	Document d;
 	//std::vector<char> chars(buffer.str(), buffer.str() + buffer.str().size() + 1u);
	//string input = buffer.str();
	d.Parse(stringbuffer.str().c_str());
	home_x = d["home_x"].GetDouble();
	home_y = d["home_y"].GetDouble();
	home_z = d["home_z"].GetDouble();
	front_belt_home = d["front_belt_home"].GetDouble();
	back_belt_home = d["back_belt_home"].GetDouble();
	//camera_offset_x = d["camera_offset_x"].GetDouble();
	//camera_offset_y = d["camera_offset_y"].GetDouble();
	//camera_offset_z = d["camera_offset_z"].GetDouble();

	camera_offset_x_init = d["camera_offset_x_init"].GetDouble();
	camera_offset_y_init = d["camera_offset_y_init"].GetDouble();
	camera_offset_z_init = d["camera_offset_z_init"].GetDouble();
	objective_offset_init = d["objective_offset_init"].GetDouble();

	camera_offset_x = camera_offset_x_init;
	camera_offset_y = camera_offset_y_init;
	camera_offset_z = camera_offset_z_init;
	objective_offset = objective_offset_init;

	front_belt = d["front_belt_init"].GetDouble();
	back_belt = d["back_belt_init"].GetDouble();
	for (int i = 0; i < 12; i++) {
		chip_offset_x[i] = d["chip_offset_x"][i].GetDouble();
	}
	for (int i = 0; i < 12; i++) {
		chip_offset_y[i] = d["chip_offset_y"][i].GetDouble();
	}
	for (int i = 0; i < 12; i++) {
		chip_offset_z[i] = d["chip_offset_z"][i].GetDouble();
	}

	objective = mag_to_index(d["objective_mag"].GetInt());
	objective_mag = d["objective_mag"].GetInt();
	
	proj_targ_x = d["proj_targ_x"].GetDouble();
	proj_targ_y = d["proj_targ_y"].GetDouble();
	proj_targ_sx = d["proj_targ_sx"].GetDouble();
	proj_targ_sy = d["proj_targ_sy"].GetDouble();
	proj_targ_r = d["proj_targ_r"].GetDouble();
	proj_adj_x = d["proj_adj_x"].GetDouble();
	proj_adj_y = d["proj_adj_y"].GetDouble();
	proj_adj_sx = d["proj_adj_sx"].GetDouble();
	proj_adj_sy = d["proj_adj_sy"].GetDouble();

	proj_adj_r = d["proj_adj_r"].GetDouble();
	
	front_belt_init = front_belt;
	back_belt_init = back_belt;
	//focus = d["focus"].GetDouble();

	//camera_offset_x_init = camera_offset_x;
	//camera_offset_y_init = camera_offset_y;
	//camera_offset_z_init = camera_offset_z;
	//objective_offset_init = objective_offset;
	//focus_init = focus;

	//Value& s = d["home_x"];

	//StringBuffer buffer;
	//Writer<StringBuffer> writer(buffer);
	//d.Accept(writer);

		// Output {"project":"rapidjson","stars":11}
	//std::cout << "Reread " << buffer.GetString() << std::endl;
	/*
		// 1. Parse a JSON string into DOM.
		const char* json = "{\"project\":\"rapidjson\",\"stars\":10}";
		Document d;
		d.Parse(json);

		// 2. Modify it by DOM.
		Value& s = d["stars"];
		s.SetInt(s.GetInt() + 1);
		*/
		// 3. Stringify the DOM
		//StringBuffer buffer;
		//Writer<StringBuffer> writer(buffer);
		//d.Accept(writer);
		
		// Output {"project":"rapidjson","stars":11}
		//std::cout << buffer.GetString() << std::endl;
	/*
	settings["home_x"] = home_x
	settings["home_y"] = home_y
	settings["camera_offset_x"] = camera_offset_x_init
	settings["camera_offset_y"] = camera_offset_y_init
	settings["focus"] = focus
	settings["toptray"] = toptray_offset
	settings["bottomtray"] = bottomtray_offset
	settings["feedrate"] = feedrate
	settings["incubation_enabled"] = incubation_enabled
	settings["fan"] = fan
	settings["objective"] = objective
	settings["xy_offsets"] = xy_offsets
	settings["mm_offsets"] = mm_offsets
	f = open("settings.txt", "w")
	f.write(json.dumps(settings))
	f.close()*/
	//cout << "done loading\n";
}

long mm_to_steps(double mm, char motor_type) {
	if (motor_type == 'x') {
		return (long)(fudge*mm * 128 * 200 / 20.0 / 2.0);
	}
	if (motor_type == 'y') {
		return (long)(fudge * mm * 128 * 200 / 20.0 / 2.0);
	}
	if (motor_type == 'o') {
		return (long)(fudge * mm * 128 * 400 / 2.0);
	}
	if (motor_type == 't') {
		return (long)(fudge * mm * 128 * 400 / 20.0 / 2.0);
	}
	if (motor_type == 'z') {
		return (long)(fudge * mm * 128 * 400 / 2.0);
	}
	//if (motor_type == 'v' || motor_type == 'w' || motor_type == 'z') {
//		return (long)(mm * 128 * 400 / 6.0);
//	}
	/*
	if (motor_type == 'z') {
		return (long)(mm*4152.88888889 / 0.5);
	}*/
}

void log_to_file(bool cmd, string command_text="") {
	//if (!logfile) {
	//	ofstream logfile("F:/themachine/log.txt", ios::app);
		//freopen("F:/themachine/log.txt", "w", stderr);
	//}
	time_t now = time(0);
	struct tm tstruct;
	char buf[80];
	tstruct = *localtime(&now);
	strftime(buf, sizeof(buf), "%Y-%m-%d-%H-%M-%S", &tstruct);
	std::string time_str(buf);
	string log_str = "";
	log_str = log_str + time_str + ",";
	if (cmd) {
		log_str = log_str + "CMD" + "," + command_text;
		log_str.erase(remove(log_str.begin(), log_str.end(), '\n'), log_str.end());
	}
	log_str = log_str + "," + std::to_string(home_x);
	log_str = log_str + "," + std::to_string(home_y);
	log_str = log_str + "," + std::to_string(camera_offset_x);
	log_str = log_str + "," + std::to_string(camera_offset_y);
	log_str = log_str + "," + std::to_string(camera_offset_z);
	//log_str = log_str + "," + std::to_string(focus);
	log_str = log_str + "," + std::to_string(co2);
	log_str = log_str + "," + std::to_string(front_rocker_angle);
	log_str = log_str + "," + std::to_string(back_rocker_angle);
	log_str = log_str + "," + std::to_string(front_noise_max);
	log_str = log_str + "," + std::to_string(back_noise_max);
	//cout << "LOGGING\n";
	//cout << log_str << "\n";
	//cerr << log_str;
	log_file << log_str << "\n";
	//fclose(stderr);
}

double steps_to_mm(long steps, char motor_type) {
	if (motor_type == 'x') {
		return (double)(steps/fudge/128.0/200.0*20.0*2.0);
	}
	if (motor_type == 'y') {
		return (double)(steps / fudge / 128.0 / 200.0 * 20.0 * 2.0);
	}
	if (motor_type == 'o') {
		return (double)(steps / fudge / 128.0 / 400.0 * 2.0);
	}
	if (motor_type == 't') {
		return (double)(steps / fudge / 128.0 / 400.0 * 20.0 * 2.0);
	}
	if (motor_type == 'z') {
		return (double)(steps / fudge / 128.0 / 400.0 * 2.0);
	}
	//if (motor_type == 'v' || motor_type == 'w' || motor_type == 'z') {
	//	return (double)(steps / 128.0 / 400.0 * 6.0);
	//}
	/*
	if (motor_type == 'z') {
		return (double)(steps / 4152.88888889*0.5);	
	}*/
}
//-Y towards door
//+X toward room door
void restart() {
	cout << "Restarting\n";	
	delete(arduino);
	arduino = new SerialPort(port_name, BAUDRATE);
	Sleep(10000);
	string final_text = "LN";
	final_text = final_text + std::to_string(lightnum) + "\n";
	final_text = final_text + "LH" + std::to_string(light) + "\n";
	//cout << "Final: " << final_text;
	std::vector<char> chars(final_text.c_str(), final_text.c_str() + final_text.size() + 1u);
	//cout << input_text << " " << input_text.size() << "\n";
	for (int i = 0; i < 8; i++) {
		motor_busy[i] = 0;
		prev_motor_busy_num[i] = 255;
		motor_busy_num[i] = 255;
	}
	bool serialerror = arduino->writeSerialPort(&chars[0], final_text.size());
}
bool motorBusy(int ind) {
	if ((motor_busy[ind] == 0) && (prev_motor_busy_num[ind] != motor_busy_num[ind])) {
		restart_mode[ind] = 0;
		return false;
	}
	else {
		double elapsedTime = ((static_cast<double>(cv::getTickCount()) - prev_motor_busy_time[ind]) / cv::getTickFrequency());
		//cout << "Restart?" << restart_mode[ind] << " " << elapsedTime << "\n";
		if (prev_motor[ind] != motor[ind]) {
			prev_motor_busy_time[ind] = static_cast<double>(cv::getTickCount());
			prev_motor[ind] = motor[ind];
		}

		else if (restart_mode[ind] == 0) {
			restart_mode[ind] = 1;
			prev_motor_busy_time[ind] = static_cast<double>(cv::getTickCount());
			prev_motor[ind] = motor[ind];
		} else 
			if (elapsedTime > 30) {
				//restart_mode[ind] = 0;
				//cout << "RESTARTING\n";
				//system("start powershell.exe Set-ExecutionPolicy RemoteSigned \n");
				//system("start powershell.exe C:\\Users\\themachine_desktop\\Documents\\alarm.ps1");
				//system("start powershell.exe D:\\themachine\\restart.ps1");
			
				//restart();
			//automate_ind = 0;
			//automating = true;
			//auto_delay_type = "SLEEP0";
		} 
		return true;
	}
}

void pause_machine() {
	if (!paused) {
		paused = true;
		std::string pause_text = "LN-1\n";
		std::vector<char> chars(pause_text.c_str(), pause_text.c_str() + pause_text.size() + 1u);
		arduino->writeSerialPort(&chars[0], pause_text.size());
	}
}

std::string normalize(const std::string &input) {
	std::string s = input;

	// 1. Convert to lowercase
	std::transform(s.begin(), s.end(), s.begin(),
		[](unsigned char c) { return std::tolower(c); });

	// 2. Remove all whitespace
	s.erase(std::remove_if(s.begin(), s.end(),
		[](unsigned char c) { return std::isspace(c); }),
		s.end());

	return s;
}

void parse_command(std::string command_text) {
	if (command_text == "\n") {
		if (program_paused == 1) {
			program_paused = 2;
		}
	}
	if (!automating) {
		last_command = command_text;
		last_command.erase(remove(last_command.begin(), last_command.end(), '\n'), last_command.end());
	}
try {

		// Vector of string to save tokens 
		string final_text = "";
		vector <string> tokens;

		// stringstream class check1 
		stringstream check1(command_text);

		string intermediate;
		// Tokenizing w.r.t. space ' ' 
		while (getline(check1, intermediate, ' '))
		{
			tokens.push_back(intermediate);
		}

		log_to_file(true, command_text);
		

		if (command_text.substr(0, 5) == "SCALE") {

			scale = stof(command_text.substr(5));
		}
		// Remote mouse events from GUI for projector mask dragging
		// MOUSEMOVE carries both coords: "MOUSEMOVE0.1234,0.5678"
		if (command_text.substr(0, 9) == "MOUSEDOWN") {
			if (image_mode == IMAGE_MICRO_PROJECTOR || image_mode == IMAGE_ALIGN) {
				drag_mode = 1;
				drag_start_x = -1;  // Sentinel: first MOUSEMOVE sets start
				drag_start_y = -1;
			}
		}
		else if (command_text.substr(0, 9) == "MOUSEMOVE") {
			if ((image_mode == IMAGE_MICRO_PROJECTOR || image_mode == IMAGE_ALIGN) && drag_mode == 1) {
				std::string coords = command_text.substr(9);
				size_t comma = coords.find(',');
				if (comma != std::string::npos) {
					int px = (int)(stof(coords.substr(0, comma)) * 1280);
					int py = (int)(stof(coords.substr(comma + 1)) * 960);
					if (drag_start_x < 0) {
						drag_start_x = px;
						drag_start_y = py;
					} else {
						proj_targ_x += px - drag_start_x;
						proj_targ_y += py - drag_start_y;
						drag_start_x = px;
						drag_start_y = py;
						update_proj = true;
					}
				}
			}
		}
		else if (command_text.substr(0, 7) == "MOUSEUP") {
			drag_mode = 0;
		}
		if (command_text.substr(0, 4) == "AUTO") {
			string chips = python + " "+prefix+"automate.py ";
			chips = chips + command_text.substr(4, command_text.length() - 4 - 1);
			cout << "Automate: " << chips << "\n";
			FILE* in = _popen(chips.c_str(), "r");
		}
		if (command_text.substr(0, 5) == "PAUSE") {
			if (program_paused==0) program_paused = 1;
			else program_paused = 0;
		}
		else if (command_text.substr(0, 7) == "RESTART") {

			restart();
		} else 
		if (command_text.substr(0, 5) == "START") {
			if (command_text.length() == 6) {
				auto_file_num = "7";
				cout << "Running default program\n";
			}
			else {
				auto_file_num = command_text.substr(5, command_text.length() - 5 - 1);
			}
			string auto_file = prefix + "automate" + auto_file_num + ".txt";
			cout << "START: " << auto_file << "\n";
			//ifstream fstm;
			//filestream.open(auto_file.c_str());
			ifstream is(auto_file);
			string str;
			//while (!automate.empty()) {
			//	automate.pop();
			//}
			automate.resize(0);
			//while (!automate.empty()) {
			//	automate_loop.pop();
			//}
			int start_auto = 0;
			while (getline(is, str))
			{
				if (auto_count>=start_auto) {
					//automate.push(str);
					automate.push_back(str);
					//automate_loop.push(str);
				}
				auto_count++;
				cout << auto_count << ": " << str << "\n";
			}
			//while (!automate.empty()) {
			//	cout << "auto: " << automate.front() << "\n";
			//	automate.pop();
			//}
			automating = true;
			automate_ind = 0;
			//static auto t = static_cast<double>(cv::getTickCount());
			prev_automate_time = static_cast<double>(cv::getTickCount());
			automate_delay = 0;
			auto_delay_type = "SLEEP0";
			auto_count = start_auto;
			proj_done = false;
		}
		else if (command_text.substr(0, 4) == "STOP") {
			automating = false;
			auto_text = "";
			next_command = "";

		}
		else if (command_text.substr(0, 4) == "BSIM") {
			if (button_mode == 0) {
				button_mode = -1;
			}
			if (button_mode==-6) {
				button_mode = 1;
			}
			
			//automating = false;
			//auto_text = "";
			//next_command = "";

		}
		else if (command_text.substr(0, 4) == "COND") {
			cond = stoi(command_text.substr(4));
			cout << "COND " << cond << "\n";
			if (cond == 1) {
				center_fail = true;
			}
		}
		else if (cond == 1 && center_fail == false) {
			bool finding_cond = true;
			while (finding_cond) {
				auto_text = automate[automate_ind];
				automate_ind++;
				auto_text.erase(std::remove(auto_text.begin(), auto_text.end(), '\n'),
					auto_text.end());
				auto_text.erase(std::remove(auto_text.begin(), auto_text.end(), '\r'),
					auto_text.end());
				if (auto_text.substr(0, 4) == "COND") {
					finding_cond = false;
					cout << "Found it!\n";
					cond = 0;
				}
				
			}
		}
		else if (command_text.substr(0, 4) == "PROJ") {
			cout << "PROJ?\n";
			//cout << command_text[4] << "???\n";
			if (command_text[4] == 'M') {
				cout << "MASK\n";
				string mask_raw = command_text.substr(5, command_text.length() - 5);
				std::string mask = normalize(mask_raw);
				mask_file_name = "proj_mask_" + mask + ".png";
				cout << "Mask " << mask << "\n";
				cout << "WTF " << command_text << "\n";
				cout << "WTF " << command_text.substr(5, command_text.length() - 5 + 1) << "\n";
				cout << prefix + "projector/proj_mask_" + mask + ".png" << "\n";
				proj_mask = imread(prefix+"projector/" + mask_file_name, 0);
				projector = proj_mask;
				proj_video_mode = false;
				proj_video_frames.clear();
				update_proj = true;
			}
			if (command_text[4] == 'V') {
				cout << "VIDEO MASK\n";
				string mask_raw = command_text.substr(5, command_text.length() - 5);
				std::string mask = normalize(mask_raw);
				proj_video_frames.clear();
				proj_video_mode = false;
				// Find numbered files: proj_mask_<mask>_1.png, proj_mask_<mask>_2.png, ...
				string base_path = prefix + "projector/proj_mask_" + mask + "_";
				for (int n = 1; ; n++) {
					string file_path = base_path + std::to_string(n) + ".png";
					cv::Mat frame = imread(file_path, 0);
					if (frame.empty()) break;
					proj_video_frames.push_back(frame);
				}
				if (!proj_video_frames.empty()) {
					proj_video_mode = true;
					mask_file_name = "proj_mask_" + mask + ".png";
					// Display last frame as preview
					projector = proj_video_frames.back();
					update_proj = true;
					cout << "Loaded " << proj_video_frames.size() << " video frames for mask " << mask << "\n";
				} else {
					cout << "No numbered frames found for mask " << mask << "\n";
				}
			}
			if (command_text[4] == 'R') {
				cout << "REF\n";
				//projector = imread("F:/themachine/projector/proj_mask.png", 0);
				projector = proj_ref;
				update_proj = true;
			}
			if (command_text[4] == 'S') {
				if (command_text[5] == '0') {
					update_proj_illum = 3;//Send current mask to be stored
				}
				else {
					cout << "MASK\n";
					string mask_raw = command_text.substr(5, command_text.length() - 5);
					std::string mask = normalize(mask_raw);
					mask_file_name = "proj_mask_" + mask + ".png";
					//update_proj_illum = 4;//Set remote mask to be illuminated
				}
			}
			if (command_text[4] == 'I') {
				if (command_text.size() == (std::string("PROJI").size()+1)) {
					cout << "we here?\n";
					proj_illum_time = 20;
					cout << "Illumination time: " << proj_illum_time << "\n";
					update_proj_illum = 1;//Send mask and illuminate
				}
				else {
					if (command_text[5] == 'S') {
						proj_illum_time = 1;//stof(command_text.substr(6));
						cout << "Illumination time: " << proj_illum_time << "\n";
						update_proj_illum = 2;//Illuminate with remote mask
					}
					else {
						cout << "or here?\n";
						proj_illum_time = stof(command_text.substr(5));
						cout << "Illumination time: " << proj_illum_time << "\n";
						update_proj_illum = 1;//Send mask and illuminate
					}
				}
			}
			if (command_text[4] == 'G') {
				//Upper left proj_targ_x: -960 proj_targ_y: -1168
				//Upper right: proj_targ_x: -2312 proj_targ_y: -1173
					if (command_text[5] == 'X') {
						float proj_tmp = stof(command_text.substr(6));
						if ((proj_tmp > -3) && (proj_tmp < 7.5)) {
							proj_targ_x = (-proj_tmp * 300 - 980);
							update_proj = true;
						}
					}
					if (command_text[5] == 'Y') {
						float proj_tmp = stof(command_text.substr(6));
						if ((proj_tmp > -12) && (proj_tmp < 3)) {
							proj_targ_y = (proj_tmp * 300 - 1170);
							update_proj = true;
						}
					}
					
					//(- 4.5 * sf - 960) = -2300
					//sf = (-2300+960)/-4.5 
				}
			if (command_text[4] == 'A') {
				if (command_text[5] == 'X') {
					proj_adj_x = stof(command_text.substr(6));// +proj_adj_x;
					//if (proj_targ_x < 0) proj_targ_x = 0;
					//if (proj_targ_x >= prev_image.size().width) proj_targ_x = prev_image.size().width;
				} else if (command_text[5] == 'Y') {
					proj_adj_y = stof(command_text.substr(6));//+proj_adj_y + 
						//if (proj_targ_y < 0) proj_targ_y = 0;
						//if (proj_targ_y >= prev_image.size().height) proj_targ_y = prev_image.size().width;
				}
				else if (command_text[5] == 'S') {
					if (command_text[6] == 'X') {
						proj_adj_sx = stof(command_text.substr(7));
						
					} else if (command_text[6] == 'Y') {
						proj_adj_sy = stof(command_text.substr(7));
						
					}
					else {
						proj_adj_sx = stof(command_text.substr(6));
						proj_adj_sy = stof(command_text.substr(6));
						
					}
				} else if (command_text[5] == 'R') {
					proj_adj_r = proj_adj_r + stof(command_text.substr(6));
					
				}
			}
			if (command_text[4] == 'T') {
				if (command_text[5] == 'X') {
					proj_targ_x = stof(command_text.substr(6));//+ proj_targ_x;
					update_proj = true;
					//if (proj_targ_x < 0) proj_targ_x = 0;
					//if (proj_targ_x >= prev_image.size().width) proj_targ_x = prev_image.size().width;
				} else
				if (command_text[5] == 'Y') {
					proj_targ_y = stof(command_text.substr(6));// + proj_targ_y;
					update_proj = true;
					//if (proj_targ_y < 0) proj_targ_y = 0;
					//if (proj_targ_y >= prev_image.size().height) proj_targ_y = prev_image.size().width;
				} else 
				if (command_text[5] == 'S') {
					if (command_text[6] == 'X') {
						proj_targ_sx = stof(command_text.substr(7));

					}
					else if (command_text[6] == 'Y') {
						proj_targ_sy = stof(command_text.substr(7));

					}
					else {
						proj_targ_sx = stof(command_text.substr(6));
						proj_targ_sy = stof(command_text.substr(6));

					}
				} else 
				if (command_text[5] == 'R') {
					proj_targ_r = proj_targ_r + stof(command_text.substr(6));
					update_proj = true;
				}
			}
			//update_proj_illum = 1;//Send mask and illuminate
			//update_proj_illum = 2;//Illuminate with remote mask
			//update_proj_illum = 3;//Send current mask to be stored
			if (update_proj_illum != 0) {
				// Video sequence mode: kick off the sequence. display_blocking
				// handles preprocessing and sending each frame on a timer.
				if (proj_video_mode && update_proj_illum == 1) {
					proj_video_index = 0;
					proj_video_sending = true;
					proj_video_next_send = 0;
					projector = proj_video_frames[0];
					update_proj = true;
					cout << "Video illumination: " << proj_video_frames.size() << " frames, "
						<< proj_illum_time << "s per frame\n";
					update_proj_illum = 0;
				}

				cv::Mat proj_output;
				if ((update_proj_illum == 1) || (update_proj_illum == 3)) {
					cv::Mat proj_clone = proj_sub.clone();

					//cv::Mat proj_output(1440, 2560, CV_8UC3, cv::Scalar(0, 0, 0));
					proj_output.create(1440, 2560, CV_8UC3);
					proj_output = cv::Scalar(0, 0, 0); // fill with black
					cv::resize(proj_clone, proj_clone, cv::Size(proj_sub.cols* proj_adj_sx, proj_sub.rows* proj_adj_sy), cv::INTER_LINEAR);

					cv::Point2f pc(proj_clone.cols / 2., proj_clone.rows / 2.);
					cv::Mat r = cv::getRotationMatrix2D(pc, proj_adj_r, 1.0);
					cv::warpAffine(proj_clone, proj_clone, r, proj_clone.size());

					//int proj_x_start = max(-proj_adj_x, 0);
					//int proj_y_start = max(-proj_adj_y, 0);
					//int proj_width = min(proj_x_start + proj_clone.cols, proj_output.cols);
					//int proj_height = min(proj_y_start + proj_clone.rows, proj_output.rows);

					//int out_x_start = max(proj_adj_x, 0);
					//int out_y_start = max(proj_adj_y, 0);
					//int out_width = out_x_start + proj_width;
					//int out_height = out_y_start + proj_height;
					int start_x = max(proj_adj_x, 0);
					int start_y = max(proj_adj_y, 0);

					int end_x = min(proj_adj_x + proj_clone.cols, proj_output.cols);
					int end_y = min(proj_adj_y + proj_clone.rows, proj_output.rows);

					//Rect proj_roi(proj_x_start, proj_y_start, proj_width, proj_height);
					//Rect output_roi(out_x_start, out_y_start, out_width, out_height);
					//cout << proj_x_start << " " << proj_y_start << " " << proj_width << " " << proj_height << " " << out_x_start << " " << out_y_start << " " << out_width << " " << out_height << "\n";
					Rect output_roi(start_x, start_y, end_x - start_x, end_y - start_y);
					//Rect output_roi(proj_adj_x, proj_adj_y, proj_adj_x+proj_clone.cols, proj_adj_y+proj_clone.rows);
					Rect proj_roi(start_x - proj_adj_x, start_y - proj_adj_y, end_x - start_x, end_y - start_y);
					//Rect proj_roi(0, 0, proj_clone.cols, proj_clone.rows);
					std::cout << "ADJ: " << proj_adj_x << " " << proj_adj_y << " " << proj_clone.cols << " " << proj_clone.rows << "\n";
					//Rect proj_roi(start_x - proj_adj_x, start_y - proj_adj_y, end_x - start_x, end_y - start_y);
					//Rect proj_roi(0, 0, proj_clone.cols, proj_clone.rows);
					// Extract ROIs
					Mat output_sub = proj_output(output_roi);
					Mat input_sub = proj_clone(proj_roi);
					//cout << start_x << " " << start_y << " " << end_x << " " << start_x << " " << end_y << " " << start_y << " " << start_x - proj_adj_x << " " << start_y - proj_adj_y << " " << end_x - start_x << " " << end_y - start_y << "\n";
					// Ensure both sub-images are of the same type
					CV_Assert(output_sub.type() == input_sub.type());
					input_sub.copyTo(output_sub);
					std::cout << "Proj adj " << proj_adj_x << " " << proj_adj_y << "\n";
				}
				StringBuffer s;
				Writer<StringBuffer> writer(s);

				writer.StartObject();
				if (update_proj_illum == 1) {
					writer.Key("image");
					writer.Bool(true);
					writer.Key("action");
					writer.String("illum");
					writer.Key("proj_time");
					writer.Double(proj_illum_time);
				}
				else if (update_proj_illum == 2) {
					writer.Key("image");
					writer.Bool(false);
					writer.Key("action");
					writer.String("illum");
					writer.Key("proj_time");
					writer.Double(proj_illum_time);

					writer.Key("proj_targ_x");
					writer.Double(proj_targ_x);
					writer.Key("proj_targ_y");
					writer.Double(proj_targ_y);
					writer.Key("proj_targ_sx");
					writer.Double(proj_targ_sx);
					writer.Key("proj_targ_sy");
					writer.Double(proj_targ_sy);
					writer.Key("proj_targ_r");
					writer.Double(proj_targ_r);
					writer.Key("proj_adj_x");
					writer.Double(proj_adj_x);
					writer.Key("proj_adj_y");
					writer.Double(proj_adj_y);
					writer.Key("proj_adj_sx");
					writer.Double(proj_adj_sx);
					writer.Key("proj_adj_sy");
					writer.Double(proj_adj_sy);
					writer.Key("proj_adj_r");
					writer.Double(proj_adj_r);

					writer.Key("image_width");
					writer.Double(prev_image.cols);
					writer.Key("image_height");
					writer.Double(prev_image.rows);
					
					writer.Key("file_name");
					writer.String(mask_file_name.c_str(), static_cast<rapidjson::SizeType>(mask_file_name.size()));
				}
				else if (update_proj_illum == 3) {
					writer.Key("image");
					writer.Bool(true);
					writer.Key("action");
					writer.String("save");
					writer.Key("file_name");
					writer.String(mask_file_name.c_str(), static_cast<rapidjson::SizeType>(mask_file_name.size()));
				}/*
				else if (update_proj_illum == 4) {
					writer.Key("image");
					writer.Bool(false);
					writer.Key("action");
					writer.String("set");
					writer.Key("proj_time");
					writer.Double(proj_illum_time);
				}*/

				writer.EndObject();

				std::string msg = s.GetString();
				//std::string type = "text";
				//std::string payload = std::to_string(proj_illum_time);
				std::string payload = "";
				zmq::message_t msg_json(msg.begin(), msg.end());
				zmq::message_t empty_payload(payload.begin(), payload.end());

				//if (proj_illum_time != 20) {
				socket_zmq.send(msg_json, zmq::send_flags::sndmore);     // first part
				if ((update_proj_illum == 1) || (update_proj_illum == 3)) {
					//}
					// First part: message type
					//input_sub.copyTo(output_sub);
					std::vector<int> compression_params = { cv::IMWRITE_PNG_COMPRESSION, 3 };
					//cv::imwrite("F:/themachine/projector/projector.png", proj_output, compression_params);
					/*
					std::vector<uchar> buf;
					if (update_proj_illum == 1) {
						cv::imwrite(prefix + "projector/projector.png", proj_output, compression_params);

						if (!cv::imencode(".png", proj_output, buf)) {
							std::cerr << "Failed to encode image.\n";
							//return false;
						}
					}
					else {
						if (0) //detect_video)
						cv::imwrite(prefix + "projector/projector.png", proj_output, compression_params);

						if (!cv::imencode(".png", proj_output, buf)) {
							std::cerr << "Failed to encode image.\n";
							//return false;
						}
					}
					//zmq::message_t msg_type("image", 5);
					//msg_type = zmq::message_t("image", 5);
					//socket_zmq.send(msg_type, zmq::send_flags::sndmore);

					// Second part: image bytes
					
					zmq::message_t img_msg(buf.data(), buf.size());
					socket_zmq.send(img_msg, zmq::send_flags::none);
					*/
					std::vector<uchar> jpg_buf;
					std::vector<int> encode_params = { cv::IMWRITE_JPEG_QUALITY, 60 };
					cv::imencode(".jpg", proj_output, jpg_buf, encode_params);
					zmq::message_t img_msg(jpg_buf.data(), jpg_buf.size());
					socket_zmq.send(img_msg, zmq::send_flags::dontwait);
				}
				else {
					socket_zmq.send(empty_payload, zmq::send_flags::none);     // last part

				}
				

				// Wait for response
				//zmq::message_t reply;
				//pull_socket.recv(reply);
				//std::string received = reply.to_string();
				//std::cout << "Received from Pi: " << received << "\n";
				/*
				// Blend the images (simple alpha blending)
				float alpha = 0.5;
				addWeighted(image_sub, 1.0 - alpha, proj_sub, alpha, 0.0, image_sub);


				//cv::Mat proj_output = cv::Mat image(1440, 2560, CV_8UC1, cv::Scalar(0));
				//cv::Mat proj_output = cv::Mat image(1440, 2560, CV_8UC1, cv::Scalar(0));
				cv::Mat proj_output(1440, 2560, CV_8UC3, cv::Scalar(0, 0, 0));
				//Rect out_roi(0, 0, proj_sub.row, proj_sub.col);
				cv::Rect out_roi(0, 0, proj_sub.cols, proj_sub.rows);
				// Extract ROIs
				Mat out_sub = proj_output(out_roi);
				*/
				/*
				input_sub.copyTo(output_sub);
				std::vector<int> compression_params = { cv::IMWRITE_PNG_COMPRESSION, 3 };
				//cv::imwrite("F:/themachine/projector/projector.png", proj_output, compression_params);
				cv::imwrite(prefix+"projector/projector.png", proj_output, compression_params);
				string scpCommand = "\"C:\\Program Files\\PuTTY\\pscp.exe\" -pw kdc17themachine "+prefix+"projector/projector.png dlp@dlp.local:/home/dlp/projector_tmp/projector.png";
				//string scpCommand = "C:\\Windows\\System32\\OpenSSH\\scp.exe F:\\themachine\\projector\\projector.png dlp@dlp.local:/";
				
				std::cout << "SCP Command: " << scpCommand << "\n";
				FILE* pipeout = _popen(scpCommand.data(), "wb");
				scpCommand = "\"C:\\Program Files\\PuTTY\\pscp.exe\" -pw kdc17themachine "+prefix+"projector\\projector.png dlp@dlp.local:/home/dlp/projector_tmp/projector.png.done";
				std::cout << "SCP Command: " << scpCommand << "\n";
				FILE* pipeout2 = _popen(scpCommand.data(), "wb");
				*/
				/*

				cv::Mat proj_clone = projector.clone();
				cvtColor(proj_clone, proj_clone, COLOR_GRAY2BGR);
				int start_x = max(proj_targ_x, 10);
				int start_y = max(proj_targ_y, 10);

				int end_x = min(proj_targ_x + proj_clone.cols, image.cols - 10);
				int end_y = min(proj_targ_y + proj_clone.rows, image.rows - 10);

				cv::resize(proj_clone, proj_clone, cv::Size(projector.cols * proj_targ_s, projector.rows * proj_targ_s), cv::INTER_LINEAR);
				cv::Point2f pc(proj_clone.cols / 2., proj_clone.rows / 2.);
				cv::Mat r = cv::getRotationMatrix2D(pc, proj_targ_r, 1.0);
				cv::warpAffine(proj_clone, proj_clone, r, proj_clone.size());

				Rect image_roi(start_x, start_y, end_x - start_x, end_y - start_y);
				Rect proj_roi(start_x - proj_targ_x, start_y - proj_targ_y, end_x - start_x, end_y - start_y);

				// Extract ROIs
				image_sub = image(image_roi);
				proj_sub = proj_clone(proj_roi);
				update_proj = false;

				// Ensure both sub-images are of the same type
				CV_Assert(image_sub.type() == proj_sub.type());

				// Blend the images (simple alpha blending)
				float alpha = 0.5;
				addWeighted(image_sub, 1.0 - alpha, proj_sub, alpha, 0.0, image_sub);
				*/
				update_proj_illum = 0;

			}
		}
		else {
			/*
			if command_text[:5] == "START" :
				auto_num = command_text[5:]
				f = open("automate" + auto_num + ".txt")
				automate = f.read().split('\n')
				f.close()
				automate = [x for x in automate if x != '' and x[0] != '#']
				print automate
				automating = True
				automate_ind = 0
				prev_automate_time = datetime.now()
				automate_delay = 0
				auto_delay_type = "SLEEP0"
				elif command_text[:4] == "STOP":
		automating = False
		automate_ind = -1
		auto_text = ""
		elif command_text[:6] == "CENTER" :
			centering = 1
			#old_frame = pygame.transform.scale(camera_image, (1280),
				#            int((float(1280) / 720) / (float(640) / 480) * 720)))
				#  old_frame = pygame.transform.rotate(old_frame, 90.0)
			#  old_frame = pygame.transform.flip(old_frame, False, True)
			#screen.blit(old_frame, (0,
		#                         -(height)+height/2))
			cv_data = pygame.surfarray.array3d(old_frame)
			cimg = cv2.cvtColor(cv_data.astype(np.uint8), cv2.COLOR_BGR2GRAY)
			hough_sf = 1.0
			hough_rad = 360.0
			circles = cv2.HoughCircles(cimg, cv2.HOUGH_GRADIENT, 1, 20,
				param1 = 50, param2 = 30, minRadius = int(round(360 * 0.95)), maxRadius = int(round(360 * 1.05)))

			hough_center = (old_frame.get_size()[0] / 2, old_frame.get_size()[1] / 2 - height / 2)
			print "Wtf"
			try :
			circles = np.uint16(np.around(circles))
			print "Got circles"
			cent_x = []
			cent_y = []
			for i in circles[0, :] :
				cent_x.append(i[0])
				cent_y.append(i[1])
				print cent_x, cent_y,
				hough_center = (int(round(np.median(cent_y))), int(round(np.median(cent_x))) - height / 2)
				print "center", hough_center
				center_x = 3
				center_y = 2
				loc_x = -(hough_center[0] / chip_sf - center_x) / 5.1
				loc_y = -(hough_center[1] / chip_sf - center_y) / 5.1
				print "xy:", loc_x, loc_y
				centered = True
				print "1"
				final_text = "X" + str(mm_to_steps(loc_y, 'y'))
				print "2"
				final_text = final_text + " Y" + str(mm_to_steps(loc_x, 'x'))
				print "3"
				final_text = final_text + " F10"
				print(final_text)
				#try :
				motors.write(final_text + "\n")
				center_time = datetime.now()
				except :
				centered = False
				pass
				#hough_center = (2 * hough_center[1], 2 * hough_center[0] - height / 2)




				elif command_text[:3] == "PIC":
		taking_pic = 1
		elif command_text[:3] == "VID" :
			taking_vid = 1
			video_length = int(command_text[3:])
			video_start_time = datetime.now()
			print "Taking video, length:", video_length

			elif command_text[0] != "H" and (command_text[0].isdigit() or command_text[1].isdigit() or command_text[1] == "-" or command_text[0] == "L") :
		elif command_text[0] == "O":
		num = int(command_text[1:])
		print num
		if num == 4 and objective == 10 :
			print "4X"
			final_text = "X" + str(mm_to_steps(1.0, 'y'))
			final_text = final_text + " Y" + str(mm_to_steps(-27.0, 'x'))
			final_text = final_text + " F10"
			print(final_text)
			motors.write(final_text + "\n")
			camera_offset_x_init = camera_offset_x_init + 27.0
			camera_offset_y_init = camera_offset_y_init - 1.0
			mm_move('9', [0, 14])
			final_text = "Z" + str(mm_to_steps(-0.1, 'z')) + " F50"
			focus_init = focus_init + 0.1
			print(final_text)
			motors.write(final_text + "\n")
			objective = 4
			store()
			if num == 10 and objective == 4:
		print "10X"
		final_text = "X" + str(mm_to_steps(-1.0, 'y'))
		final_text = final_text + " Y" + str(mm_to_steps(27.0, 'x'))
		final_text = final_text + " F10"
		print(final_text)
		motors.write(final_text + "\n")
		camera_offset_x_init = camera_offset_x_init - 27.0
		camera_offset_y_init = camera_offset_y_init + 1.0
		mm_move('9', [0, -14])
		final_text = "Z" + str(mm_to_steps(0.1, 'z')) + " F50"
		focus_init = focus_init - 0.1
		print(final_text)
		motors.write(final_text + "\n")
		objective = 10
		store()
			else:
		final_feedrate = 0
		got_error = False
		new_feedrate = feedrate
		#new_bottomtray = bottomtray
		#new_toptray = toptray
		#new_focus = focus
		#new_camera_offset_x = camera_offset_x
		#new_camera_offset_y = camera_offset_y
		*/

		//laser_text = "X" + std::to_string(xlasertravel) + " " + "Y" + std::to_string(ylasertravel) + " " + "F10\n";
			// Printing the token vector 
			for (int i = 0; i < tokens.size(); i++) {
				if (tokens[i][0] == 'V') {
					run_hough_circles = false;
					run_hough_lines = false;
					video_frame = 0;
					recording_video = true;
					//cout << "WTF length " << tokens[i].length() << "\n";
					//float frame_time = stof(tokens[i].substr(1));
					//std::cout << "WTF??? " << frame_time << "\n";	
					//std::cout << "WTF2??? " << frame_time * fps << "\n";
					//std::cout << "Size " << tokens.size() << "\n";
					//No number gives length 2 if Size is 1
					//Number gives min length 3 if size is 1
					//Number gives min length 2 if min size is 2
					if ((tokens[i].length() > 2) || ((tokens[i].length() > 1) && (tokens.size()>1))) {
						//std::string fps_str = std::to_string(fps);
						//std::cout << "WTF1 " << tokens[i] << "\n";
						//std::cout << "WTF2 " << tokens[i].substr(1) << "\n";
						//std::cout << "WTF3 " << stoi(tokens[i].substr(1)) << "\n";
						//std::cout << "wtf " << stoi(tokens[i].substr(1)) << " " << fps << "\n";
						num_frames = int(stof(tokens[i].substr(1))*fps);
						if (num_frames < 0) {
							num_frames = 0;
						}
						if (num_frames > MAX_VIDEO_FRAMES) {
							num_frames = MAX_VIDEO_FRAMES;
						}
				
					}
					else {
						num_frames = MAX_VIDEO_FRAMES;
					}
					std::cout << "Starting video, " << num_frames << " frames\n";
				} else if (tokens[i][0] == 'P') {
					//cout << tokens[i].length() << "\n";
					if (tokens[i].length() > 2) {
						pic_dir = tokens[i].substr(1, tokens[i].size() - 2);
					}
					else {
						pic_dir = "";
					}
					taking_picture = true;
					std::cout << "Taking picture\n";
					/*

					//util_image::raw_to_rgb(pBuffRaw_[0], 0, pBuffRGB_, 0, iWidth_*iHeight_, bitsPerPix_);
					//cv::Mat image(iHeight_, iWidth_, CV_8UC3, pBuffRGB_);

					
					*/
				}
				else if (tokens[i][0] == 'S') {
					auto deviceList = video_in->get_devices_list();
					cout << "Video size: " << stoi(tokens[i].substr(1)) << "\n";
					//video_in->dshow_.
					//video_in->stop();
					video_in->set_format(stoi(tokens[i].substr(1)));
					video_in->setup(deviceList[0]);
					video_in->run();
				}
				else if (tokens[i][0] == 'E') {
					//cout << "string " << input_text << " " << input_text.substr(1) << "\n";
					exposure = stoi(tokens[i].substr(1));
					video_in->set_exposure(exposure);
				} else if (tokens[i][0] == 'D') {
					string dac_text = tokens[i];
					cout << "DAC: " << dac_text;
					std::vector<char> chars(dac_text.c_str(), dac_text.c_str() + dac_text.size() + 1u);
					//cout << input_text << " " << input_text.size() << "\n";
					bool serialerror = dacArduino->writeSerialPort(&chars[0], dac_text.size());
				} else if (tokens[i][0] == 'L') {
					if (tokens[i][1] == 'N') {
						final_text = "LN";
						if (tokens[i][2] == 'F') {
							final_text = final_text + std::to_string(stoi(tokens[i].substr(3))+5) + "\n";
						}
						else if (tokens[i][2] == 'B') {
							final_text = final_text + std::to_string(stoi(tokens[i].substr(3))-1) + "\n";
						}
						else {
							final_text = final_text + std::to_string(stoi(tokens[i].substr(2))) + "\n";
						}

					}
					else if (tokens[i][1] == 'H') {
						light = static_cast<int>(stof(tokens[i].substr(2)) * 4095);
						if (light > 4095) light = 4095;
						if (light < 0) light = 0;
						final_text = final_text + " LH" + std::to_string(light);
					}
					else if (tokens[i][1] == 'A') {
						light_a = static_cast<int>(stof(tokens[i].substr(2)) * 4095);
						if (light_a > 4095) light_a = 4095;
						if (light_a <  0) light_a = 0;
						final_text = final_text + " LA" + std::to_string(light_a);
					}
					else if (tokens[i][1] == 'B') {
						light_b = static_cast<int>(stof(tokens[i].substr(2)) * 4095);
						if (light_b > 4095) light_b = 4095;
						if (light_b < 0) light_b = 0;
						final_text = final_text + " LB" + std::to_string(light_b);
					}
					else if (tokens[i][1] == 'L') {
						string light_l_n;
						int offset;

						// Check if the character at index 2 is a digit (e.g., "LL0.5") or a letter (e.g., "LLA0.5")
						if (isdigit(tokens[i][2])) {
							// Generic Mode (LL0 - LL1): Use objective to decide A, B, or C
							offset = 2; // The number starts immediately after "LL"
							if (objective == 0) light_l_n = "A";
							else if (objective == 1) light_l_n = "B";
							else if (objective == 2) light_l_n = "C";
							else light_l_n = "A"; // Default fallback if objective is out of range
						} 
						else {
							// Explicit Mode (LLA0 - LLC1): Use the letter provided in the string
							offset = 3; // The number starts after "LLA"
							light_l_n = string(1, tokens[i][2]);
						}

						// Parse the float using the calculated offset
						int light_l = static_cast<int>(stof(tokens[i].substr(offset)) * 65535);

						// Clamping logic (unchanged)
						if (light_l > 65535) light_l = 65535;
						if (light_l < 0) light_l = 0;

						final_text = final_text + " LL" + light_l_n + std::to_string(light_l);
						cout << "Oblique:" << final_text << "\n";
					}
				}
				else if (tokens[i][0] == 'X') {
					
			
					if ((move_mode == MOVE_MOTOR || move_mode == MOVE_FEEDBACK)) {
						
						final_text = final_text + " X" + std::to_string(mm_to_steps(stof(tokens[i].substr(1)), 'x'));
						//motor_busy[6] = true;
						prev_motor_busy_num[6] = motor_busy_num[6];
						prev_motor_busy_num[7] = motor_busy_num[7];
						if (command_text.find('F') == std::string::npos) {
							//final_text = final_text + " F10";
						}

						if (move_mode == MOVE_FEEDBACK) {
							chip_feedback_x += stof(tokens[i].substr(1)) * 400;
							while (chip_feedback_x > 13.2 * 200) {
								chip_feedback_x -= 13.2 * 400;
							}
							while (chip_feedback_x < -13.2 * 200) {
								chip_feedback_x += 13.2 * 400;
							}
						}
					}
					else if (move_mode == MOVE_REF) {
						chip_pos_x = stof(tokens[i].substr(1));
					}
				}
				else if (tokens[i][0] == 'Y') {
					
					if ((move_mode == MOVE_MOTOR) || (move_mode == MOVE_FEEDBACK)) {
						//motor_busy[0] = true;
						final_text = final_text + " Y" + std::to_string(mm_to_steps(stof(tokens[i].substr(1)), 'y'));
						prev_motor_busy_num[3] = motor_busy_num[3];
						if (command_text.find('F') == std::string::npos) {
							//final_text = final_text + " F10";
						}
						if (move_mode == MOVE_FEEDBACK) {
							chip_feedback_y -= stof(tokens[i].substr(1)) * 400;
							//}
							while (chip_feedback_y > 6.5 * 200) {
								chip_feedback_y -= 6.5 * 400;
							}
							while (chip_feedback_y < -6.5 * 200) {
								chip_feedback_y += 6.5 * 400;
							}
						}
					}
					else if (move_mode == MOVE_REF) {
						chip_pos_y = stof(tokens[i].substr(1));
					}
				}
				else if (tokens[i][0] == 'Z') {
					if (tokens[i][1] == 'A') {
						prev_motor_busy_num[0] = motor_busy_num[0];
						//prev_motor_busy_num[1] = motor_busy_num[1];
						final_text = final_text + " ZA" + std::to_string(mm_to_steps(stof(tokens[i].substr(2)), 'z'));
						if (command_text.find('F') == std::string::npos) {
							//final_text = final_text + " F100";
						}
					}
					else if (tokens[i][1] == 'B') {
						//prev_motor_busy_num[0] = motor_busy_num[0];
						prev_motor_busy_num[1] = motor_busy_num[1];
						final_text = final_text + " ZB" + std::to_string(mm_to_steps(stof(tokens[i].substr(2)), 'z'));
						if (command_text.find('F') == std::string::npos) {
							//final_text = final_text + " F100";
						}
					}
					else {
						prev_motor_busy_num[0] = motor_busy_num[0];
						prev_motor_busy_num[1] = motor_busy_num[1];
						final_text = final_text + " Z" + std::to_string(mm_to_steps(stof(tokens[i].substr(1)), 'z'));
						if (command_text.find('F') == std::string::npos) {
							//final_text = final_text + " F100";
						}
					}
				}
				else if (tokens[i][0] == 'R') {
					if (tokens[i][2] != 'V') {
						if (tokens[i][1] == 'B') prev_motor_busy_num[4] = motor_busy_num[4];
						if (tokens[i][1] == 'F') prev_motor_busy_num[5] = motor_busy_num[5];
					}
					final_text = final_text + " " + tokens[i][0] + tokens[i][1] + std::to_string(mm_to_steps(stof(tokens[i].substr(2)), 't'));
					if (command_text.find('F') == std::string::npos) {
						final_text = final_text + " F100";
					}
				}
				else if (tokens[i][0] == 'O') {
					//Positive number towards higher magnification
					prev_motor_busy_num[2] = motor_busy_num[2];
					final_text = final_text + " O" + std::to_string(mm_to_steps(stof(tokens[i].substr(1)), 'o'));
					if (command_text.find('F') == std::string::npos) {
						//final_text = final_text + " F1500";
					}
				}
				/*
				else if (tokens[i][0] == 'Z') {
					final_text = final_text + " 3X" + std::to_string(mm_to_steps(stof(tokens[i].substr(1)), 'z'));
					final_text = final_text + " 3Y" + std::to_string(-mm_to_steps(stof(tokens[i].substr(1)), 'z'));

					if (command_text.find('F') == std::string::npos) {
						final_text = final_text + " F50";
					}
				}*/
				else if (tokens[i][0] == 'H') {
					if (tokens[i][1] == 'O') {
						int mag = 4;
						objective = mag_to_index(mag);
						objective_mag = mag;
						objective_offset_init = -home_obj - objective_offset_driver;
						cout << "HO: objective_offset_driver=" << objective_offset_driver
							<< " objective_offset_init=" << objective_offset_init << "\n";
						
						store();
					}
					if (tokens[i][1] == 'X') {
						camera_offset_x_init = -home_x - camera_offset_x_driver;
						//cout << "WTF " << camera_offset_x_init << " " << home_x << " " << camera_offset_x_driver << "\n";
					}
					if (tokens[i][1] == 'Y') {
						camera_offset_y_init = -home_y - camera_offset_y_driver;
					}
					if (tokens[i][1] == 'Z') {
						camera_offset_z_init = -home_z - camera_offset_z_driver;
						//focus_init = -home_z -steps_to_mm(small_stepper[Z_MOTOR], 'z');
					}					
					if (tokens[i][1] == 'C') {
						if (tokens[i][2] == 'O') {
							//I
							//O
							//L
							//R
							if (tokens[i][3] == 'I') orientations[current_chip] = TAB_IN;
							if (tokens[i][3] == 'O') orientations[current_chip] = TAB_OUT;
							if (tokens[i][3] == 'L') orientations[current_chip] = TAB_LEFT;
							if (tokens[i][3] == 'R') orientations[current_chip] = TAB_RIGHT;
						}
						else {
							if (tokens[i][2] == 'F') {
								current_chip = stoi(tokens[i].substr(3)) + 5;
							}
							else if (tokens[i][2] == 'B') {
								current_chip = stoi(tokens[i].substr(3)) - 1;
							}
							else {
								current_chip = stoi(tokens[i].substr(2));
							}

							chip_offset_x[current_chip] = camera_offset_x;
							chip_offset_y[current_chip] = camera_offset_y;
							chip_offset_z[current_chip] = camera_offset_z;
							chip_yaw[current_chip] = start_yaw;
							chip_sf[current_chip] = start_sf;
							cout << current_chip << " " << chip_offset_x[current_chip] << " " << chip_offset_y[current_chip] << " " << chip_yaw[current_chip] << "\n";
							well_number = 1;
							store();
						}
					}
					if (tokens[i][1] == 'R') {
						if (tokens[i][2] == 'F') {
							front_belt_init = - front_belt_home - front_belt_driver;	
						}
						if (tokens[i][2] == 'B') {
							back_belt_init = -back_belt_home - back_belt_driver;
						}
					}
					//if (tokens[i][1] == 'W') {
					//	current_chip = stoi(tokens[i].substr(2));
					//	chip_offset_x[current_chip] = camera_offset_x;
					//	chip_offset_y[current_chip] = camera_offset_y;
					//	//cout << current_chip << " " << chip_offset_x[current_chip] << " " << chip_offset_y[current_chip] << "\n";
					//}
				}
				else if (tokens[i][0] == 'G') {
					if (tokens[i][1] == 'O') {
						int prev_objective = objective;
						int mag = stoi(tokens[i].substr(2));
						objective = mag_to_index(mag);
						objective_mag = mag;

						if (objective != prev_objective) {
							float loc_o = -objective_pos[objective] - objective_offset;
							cout << "GO" << mag << " (index " << objective << "): objective_pos=" << objective_pos[objective]
								<< " objective_offset=" << objective_offset
								<< " loc_o=" << loc_o
								<< " steps=" << mm_to_steps(loc_o, 'o') << "\n";
							final_text = final_text + " O" + std::to_string(mm_to_steps(loc_o, 'o'));
							prev_motor_busy_num[2] = motor_busy_num[2];

							//float loc_z = objective_z[objective] - camera_offset_z;
							//float loc_z = 0.1;
							//if (objective == 0) {
							//	loc_z = -loc_z;
							//}

							//final_text = final_text + " Z" + std::to_string(mm_to_steps(loc_z, 'z'));
							//prev_motor_busy_num[0] = motor_busy_num[0];
							//prev_motor_busy_num[1] = motor_busy_num[1];
						}

					} /*else if (tokens[i][1] == 'R') {
						float belt = stof(tokens[i].substr(3));
						if (tokens[i][2] == 'F') {
							float loc_r = -front_belt_home - front_belt + belt;
							final_text = final_text + " RF" + std::to_string(mm_to_steps(loc_r, 't'));
							prev_motor_busy_num[5] = motor_busy_num[5];
						}
						else {
							float loc_r = -back_belt_home - back_belt + belt;
							final_text = final_text + " RB" + std::to_string(mm_to_steps(loc_r, 't'));
							prev_motor_busy_num[4] = motor_busy_num[4];
						}
					
					else {
					
						int go_mode = 0;
						if (tokens[i][1] == 'C') {
							if (tokens[i][2] == 'Z') {
								go_mode = 1;
							}
							else {
								if (tokens[i][2] == 'F') {
									current_chip = stoi(tokens[i].substr(3))+5;
								}
								else if (tokens[i][2] == 'B') {
									current_chip = stoi(tokens[i].substr(3))-1;
								}
								else {
									current_chip = stoi(tokens[i].substr(2));
								}
								well_number = 1;
							}
						}
						else {
							well_number = stoi(tokens[i].substr(1));
							//float loc_x = -home_x - camera_offset_x - rot_x;
							//float loc_y = -home_y - camera_offset_y - rot_y;
							//cout << loc_x << " " << loc_y << "\n";
							//final_text = final_text + " X" + std::to_string(mm_to_steps(loc_x, 'x'));
							//final_text = final_text + " Y" + std::to_string(mm_to_steps(loc_y, 'y'));
						}
						
						if (go_mode == 0) {
							double xy_offsets[8][2] = { 0 };
							float x_spacing = 6.4 * chip_sf[current_chip];// 1.04;// 1.029;
							float y_spacing = 13.155 * chip_sf[current_chip];
							
							xy_offsets[0][0] = 0;
							xy_offsets[1][0] = -x_spacing;
							xy_offsets[2][0] = -x_spacing * 2;
							xy_offsets[3][0] = -x_spacing * 3;
							xy_offsets[4][0] = 0;
							xy_offsets[5][0] = -x_spacing;
							xy_offsets[6][0] = -x_spacing * 2;
							xy_offsets[7][0] = -x_spacing * 3;

							xy_offsets[0][1] = 0;
							xy_offsets[1][1] = 0;
							xy_offsets[2][1] = 0;
							xy_offsets[3][1] = 0;
							xy_offsets[4][1] = -y_spacing;
							xy_offsets[5][1] = -y_spacing;
							xy_offsets[6][1] = -y_spacing;
							xy_offsets[7][1] = -y_spacing;

							cout << "Orientation: " << orientations[current_chip] << " " << chip_yaw[current_chip] << "\n";
							//float angle = 0;// -3.0 * CV_PI / 180.0f;
							float rot_x = cos(chip_yaw[current_chip]+orientations[current_chip]) * xy_offsets[well_number - 1][1] - sin(chip_yaw[current_chip] + orientations[current_chip]) * xy_offsets[well_number - 1][0];
							float rot_y = sin(chip_yaw[current_chip]+orientations[current_chip]) * xy_offsets[well_number - 1][1] + cos(chip_yaw[current_chip] + orientations[current_chip]) * xy_offsets[well_number - 1][0];
							//cout << xy_offsets[well_number - 1][0] << " " << xy_offsets[well_number - 1][1] << "\n";
							float loc_x = -home_x + chip_offset_x[current_chip] - camera_offset_x - rot_x;
							float loc_y = -home_y + chip_offset_y[current_chip] - camera_offset_y - rot_y;

							//cout << loc_x << " " << loc_y << "\n";
							final_text = final_text + " X" + std::to_string(mm_to_steps(loc_x, 'x'));
							final_text = final_text + " Y" + std::to_string(mm_to_steps(loc_y, 'y'));
							prev_motor_busy_num[3] = motor_busy_num[3];
							prev_motor_busy_num[6] = motor_busy_num[6];
							prev_motor_busy_num[7] = motor_busy_num[7];
							//if (tokens[i][1] == 'C') {
							//}
							//print "GO"
							//#final_text = "X" + str(backlash_target[1])
							//final_text = final_text + " Y" + str(backlash_target[0])
							//final_text = final_text + " F10"
							//print(final_text)
							//motors.write(final_text + "\n")
						}
						else {
							float loc_z = -home_z + chip_offset_z[current_chip] - camera_offset_z;
							final_text = final_text + " Z" + std::to_string(mm_to_steps(loc_z, 'z'));
							prev_motor_busy_num[0] = motor_busy_num[0];
							prev_motor_busy_num[1] = motor_busy_num[1];

						}
						
					}*/
				}
				else if (tokens[i][0] == 'I') {
					if (tokens[i][1] == 'I') {
						final_text = final_text + " " + tokens[i].substr(1);
					}
					else if (tokens[i][1] == 'A') {
						if (tokens[i][2] == 'P') {
							cout << "align_mode 1\n";
							align_mode = 1;
							final_text = "\n";
						}
						if (tokens[i][2] == 'M') {
							cout << "align_mode 2\n";
							align_mode = 2;
							final_text = "\n";
						}
					}
					else 
					//if (tokens[i][1] == '0') {
					//	video_in->stop();
					//}

					if (tokens[i][1] == 'F') {
						run_focus = true;
						running = true;
						focus_mode = 1;
						image_attempts = 0;
						//focus_level = 0;
						
						prev_focus_time = static_cast<double>(cv::getTickCount());
						//parse_command("Z-0.2\n");
						//parse_command("Z-0.5\n");
						//focus_delay = 8.0;
						//Go down
					}
					else if (tokens[i][1] == 'L') {
						lighting_type = stoi(tokens[i].substr(2));
						lighting_mode = 1;
						image_attempts = 0;
						//cout << "Latency start\n";
						//cout << "Latency start\n";
						//latency_time = static_cast<double>(cv::getTickCount());
						//latency = true;
						//parse_command("LH0\n");
						run_lighting = true;
						running = true;\
						focus_level = 0;
						prev_lighting_time = static_cast<double>(cv::getTickCount());
						/*
						if (lighting_type==2) {
							parse_command("LH255\n");
							//parse_command("LH0\n");
							//lighting = 0;
							lighting = 255;
						}
						else if (lighting_type == 3) {
							parse_command("LH255\n");
							lighting = 255;
						}*/
						
						//if (lighting_type == 0) {
							prev_lighting_time = static_cast<double>(cv::getTickCount());
							parse_command("LH64\n");
							lighting = 64;
							//double min, max;
							//minMaxLoc(image, &min, &max);
							lighting_ind = 0;
							//lighting_min[lighting_ind] = min;
							//lighting_max[lighting_ind] = max;
							//lighting_ind++;
						//}
						//else if (lighting_type == 1) {
							//prev_lighting_time = static_cast<double>(cv::getTickCount());
							//parse_command("LH64\n");
							//lighting = 255;
							//double min, max;
							//minMaxLoc(image, &min, &max);
							//lighting_ind = 0;
							//lighting_min[lighting_ind] = min;
							//lighting_max[lighting_ind] = max;
							//lighting_ind++;
						//}
					}
					else if (tokens[i][1] == 'C') {
						run_hough_circles = true;
						run_center = 1;
						running = true;
						center_count = 0;
						prev_hough_time = static_cast<double>(cv::getTickCount());
						//prev_lighting_time = static_cast<double>(cv::getTickCount());
						//parse_command("LH0\n");
						//lighting = 0;
					}
					else if (tokens[i][1] == 'S') {
						cout << "hough_conf_total " << hough_conf_total << " well_number " << well_number << + "\n";
						if (hough_conf_total > 10) {
							if (well_number == 1) {
								cout << "Reset home\n";
								chip_offset_x[current_chip] = camera_offset_x;
								chip_offset_y[current_chip] = camera_offset_y;
								chip_offset_z[current_chip] = camera_offset_z;
								chip_yaw[current_chip] = start_yaw;
								chip_sf[current_chip] = start_sf;
								store();
							}
							else if ((well_number > 1) && (well_number <=4)) {
								cout << "Reset yaw\n";
								//chip_yaw[current_chip] = -atan2((-136.283 + 135.87), (-56.5844 + 63.1594));
								chip_yaw[current_chip] = atan2((chip_offset_x[current_chip] - camera_offset_x), -(chip_offset_y[current_chip] - camera_offset_y)) - orientations[current_chip];

								chip_sf[current_chip] = sqrt((chip_offset_x[current_chip] - camera_offset_x)* (chip_offset_x[current_chip] - camera_offset_x) +
									(chip_offset_y[current_chip] - camera_offset_y)* (chip_offset_y[current_chip] - camera_offset_y));
								chip_sf[current_chip] = chip_sf[current_chip] / (6.4*(well_number-1));
								//cout << "well number" << "\n";
								cout << camera_offset_x << " " << camera_offset_y << " " << camera_offset_z << "\n";
								//-135.87 -63.1594 0.551504
								cout << chip_offset_x[current_chip] << " " << chip_offset_y[current_chip] << " " << chip_offset_z[current_chip] << "\n";
								// -136.284 -56.5844 0.551504
								cout << chip_yaw[current_chip] << "\n";
								cout << "CHIP_SF: " << chip_sf[current_chip] << "\n";
								//chip_sf[current_chip] = start_sf;
							}
						}
						//run_hough_circles = true;
						//run_center = 1;`
						//running = true;
						//center_count = 0;
						//prev_hough_time = static_cast<double>(cv::getTickCount());
						//prev_lighting_time = static_cast<double>(cv::getTickCount());
						//parse_command("LH0\n");
						//lighting = 0;
					}
					else 
					{
						image_mode = stoi(tokens[i].substr(1));
					}
				}
				else if (tokens[i][0] == 'M') {
					move_mode = stoi(tokens[i].substr(1));
					if (move_mode == MOVE_REF) {
						chip_pos_x = chip_pos_x + chip_feedback_x;
						chip_pos_y = chip_pos_y + chip_feedback_y;
						chip_feedback_x = 0;
						chip_feedback_y = 0;
					}
				}
				/*
		elif i[0] in['1', '2', '3', '4', '5', '6', '7', '8', '9'] :
			if i[1] == 'X' :
				mm_move(i[0], [float(i[2:]), 0])
				elif i[1] == 'Y' :
				mm_move(i[0], [0, float(i[2:])])
			else :
				final_text = i[0] + "W" + str(mm_to_steps(float(i[2:]), 'w')) + " F100"
				if "F" not in command_text :
		final_text = final_text + " F100"
		new_feedrate = 50

		elif i[0] == '0' :
			mm_moving_axis = i[1]
			mm_moving_dist = float(i[2:])
			mm_moving_status = -1
			mm_moving = True
			mm_moving_time = datetime.now()
			elif i[0] == "L":
		if i[1] == "H" :
			final_text = final_text + " LH" + i[2:]
			elif i[1] == "L" :
			final_text = final_text + " LL" + i[2:]
		else :
			final_text = final_text + " LH" + i[1:] + " LL" + i[1:]
			#final_text = final_text + " LH" + i[1:]
				else:*/
				else {
					final_text = final_text + " " + tokens[i];
				}
			}
			final_text = final_text + "\n";
			//motors.write(final_text + "\n")
			
			cout << "Final: " << final_text;
			std::vector<char> chars(final_text.c_str(), final_text.c_str() + final_text.size() + 1u);
			//cout << input_text << " " << input_text.size() << "\n";
			bool serialerror = arduino->writeSerialPort(&chars[0], final_text.size());
			//cout << "Error: " << serialerror << "\n";
			/*
			else:
			if command_text[0] == "H" :
				print "Home"
				if command_text[1] == "X" :
					camera_offset_x_init = -home_x - camera_offset_x_driver
					xy_offsets[0][0] = 0
					xy_offsets[1][0] = x_spacing
					xy_offsets[2][0] = x_spacing * 2
					xy_offsets[3][0] = x_spacing * 3
					xy_offsets[4][0] = 0
					xy_offsets[5][0] = x_spacing
					xy_offsets[6][0] = x_spacing * 2
					xy_offsets[7][0] = x_spacing * 3
					#home_x += float(typing_text[2:])
					if command_text[1] == "Y":
			camera_offset_y_init = -home_y - camera_offset_y_driver
			xy_offsets[0][1] = 0
			xy_offsets[1][1] = 0
			xy_offsets[2][1] = 0
			xy_offsets[3][1] = 0
			xy_offsets[4][1] = y_spacing
			xy_offsets[5][1] = y_spacing
			xy_offsets[6][1] = y_spacing
			xy_offsets[7][1] = y_spacing
			#home_y -= float(typing_text[2:])
			if command_text[1] == "T":
			toptray_offset = -toptray_driver
			if command_text[1] == "B" :
				bottomtray_offset = -bottomtray_driver
				if command_text[1] == "Z" :
					focus_init = -steps_to_mm(zmotor_pos, 'z')
					if command_text[1] in["1", "2", "3", "4", "5", "6", "7", "8"] :
						print "Micro"
						num = int(command_text[1:])
						xy_offsets[num - 1][0] = 0
						xy_offsets[num - 1][1] = 0
						loc_x, loc_y = go_to(num)
						xy_offsets[num - 1][0] = -home_x - camera_offset_x
						xy_offsets[num - 1][1] = -home_y - camera_offset_y
						#loc_y = -home_y - camera_offset_y - xy_offsets[num - 1][1]
						print xy_offsets[num - 1][1], -home_y, -camera_offset_y, -loc_y

						store()
						elif command_text[0] == "I":

			*/
		}
	}
	catch (exception &err) {
		cout << "Invalid command\n";
	}
}
# define M_PI           3.14159265358979323846  /* pi */
Mat chip = imread(prefix+"chipsketch.png", CV_LOAD_IMAGE_COLOR);



//bool drewChip = false;
/*
void drawChip(Mat &chip) {
	//if (!drewChip) {
		//cout << "Drawing!";
		//Mat chip(detected_edges.rows, detected_edges.cols, CV_8UC3, Scalar(0, 0, 0));
		Point pt1, pt2;
		pt1.x = 0;
		pt1.y = 0;
		pt2.x = 50;
		pt2.y = 50;
		line(chip, pt1, pt2, Scalar(0, 0, 255), 3, LINE_AA);
		//drewChip = true;
	//}
}*/

void moveLaser() {
	static auto t = static_cast<double>(cv::getTickCount());
	double elapsedTimeMs = ((static_cast<double>(cv::getTickCount()) - t) / cv::getTickFrequency()) * 1000;
	if (elapsedTimeMs >= 100) {
		cout << "Move laser\n";

		//Up and left: 135
		//Down and left: -135
		//Up and right: 45
		//Down and right: -45

		std::string laser_text = "";
		double xlasertravel = 0;
		double ylasertravel = 0;
		if (0) {//flowmag > 2) {
			//cout << "Angle compare: " << flowang << " " << laserang << "\n";
			//flowang = laserang;
			double anglediff = flowang - laserang;
			double intanglediff = integralang - laserang;
			if (anglediff > M_PI) {
				anglediff -= (2 * M_PI);
			}
			if (anglediff < -M_PI) {
				anglediff += (2 * M_PI);
			}
			if (intanglediff > M_PI) {
				intanglediff -= (2 * M_PI);
			}
			if (intanglediff < -M_PI) {
				intanglediff += (2 * M_PI);
			}
			//anglediff = 0;

			//cout << "Angle diff " << anglediff*180/M_PI << "\n";
			if (anglediff > 10) anglediff = 10;
			if (anglediff < -10) anglediff = -10;
			if (intanglediff > 2) intanglediff = 2;
			if (intanglediff < -2) intanglediff = -2;
			laserang = origlaserang - 0.75*anglediff - 0.2*intanglediff;
			if (laserang > M_PI) {
				laserang -= (2 * M_PI);
			}
			if (laserang < -M_PI) {
				laserang += (2 * M_PI);
			}
			cout << "Laser " << origlaserang * 180 / M_PI << " flow " << flowang * 180 / M_PI << " diff " << anglediff * 180 / M_PI << " modified " << laserang * 180 / M_PI << " integralang " << integralang * 180 / M_PI << " intanglediff " << intanglediff * 180 / M_PI << "\n";


			ylaserinc = laserincmag * sin(laserang);
			xlaserinc = laserincmag * cos(laserang);
			ylaser = lasermag * sin(laserang);
			xlaser = lasermag * cos(laserang);
			double laserintmag = sqrt(ylaserint*ylaserint + xlaserint * xlaserint);
			cout << "Int mag " << laserintmag << " lasermag " << lasermag << "\n";
			ylaserint = laserintmag * sin(laserang);
			xlaserint = laserintmag * cos(laserang);


		}
		if (((xlaserinc >= 0) && (xlaser > xlaserinc)) || ((xlaserinc < 0) && (xlaser < xlaserinc))) {
			xlaserint = xlaserint + xlaserinc;
			xlaser = xlaser - xlaserinc;
			if (xlaserint > laserincmag) {
				xlaserint -= laserincmag;
				xlasertravel = laserincmag;
			}
			else if (xlaserint < -laserincmag) {
				xlaserint += laserincmag;
				xlasertravel = -laserincmag;
			}
		}
		if (((ylaserinc >= 0) && (ylaser > ylaserinc)) || ((ylaserinc < 0) && (ylaser < ylaserinc))) {
			ylaserint = ylaserint + ylaserinc;
			ylaser = ylaser - ylaserinc;
			if (ylaserint > laserincmag) {
				ylaserint -= laserincmag;
				ylasertravel = laserincmag;
			}
			else if (ylaserint < -laserincmag) {
				ylaserint += laserincmag;
				ylasertravel = -laserincmag;
			}
		}
		lasermag = sqrt(xlaser*xlaser + ylaser * ylaser);
		if (fabs(ylaser) <= laserincmag && fabs(xlaser) <= laserincmag) {
			lasermoving = 0;
		}



		laser_text = "X" + std::to_string(xlasertravel) + " " + "Y" + std::to_string(ylasertravel) + " " + "F10\n";
		//xtravel = xintegral - xlaser;
		//ytravel = yintegral - ylaser;

		//travelmag = sqrt(xtravel*xtravel + ytravel * ytravel);

		//xtravel
		//laser_text = "X1 Y1 F10\n";
		//cout << x - laser.x << " " << y - laser.y << "\n";
		//laser_text = "X" + std::to_string((x - laser.x)) + " " + "Y" + std::to_string(-(y - laser.y)) + " " + "F10\n";
		cout << laser_text << "\n";
		cout << "xlaser " << xlaser << " laserint " << xlaserint << " laserinc " << xlaserinc << "\n";
		cout << "ylaser " << ylaser << " laserint " << ylaserint << " laserinc " << ylaserinc << "\n";

		std::vector<char> chars(laser_text.c_str(), laser_text.c_str() + laser_text.size() + 1u);
		arduino->writeSerialPort(&chars[0], laser_text.size());
		t = static_cast<double>(cv::getTickCount());
	}
}
void mouse_callback(int  event, int  x, int  y, int  flag, void *param)
{
	//cout << "here?\n";
	if (image_mode == IMAGE_MICRO_PROJECTOR || image_mode == IMAGE_ALIGN) {
		if (event == EVENT_MOUSEMOVE) {
			if (drag_mode == 1) {
				//cout << "(" << x-drag_start_x << ", " << y-drag_start_y << ")" << endl;
				proj_targ_x = proj_targ_x + x - drag_start_x;
				proj_targ_y = proj_targ_y + y - drag_start_y;
				drag_start_x = x;
				drag_start_y = y;
				cout << proj_targ_x << " " << proj_targ_y << "\n";
				update_proj = true;
			}
		}
		if (event == EVENT_LBUTTONDOWN) {
			cout << "start drag\n";
			drag_mode = 1;
			drag_start_x = x;
			drag_start_y = y;
		}
		if (event == EVENT_LBUTTONUP) {
			cout << "end drag\n";
			drag_mode = 0;
		}
		//if (event == EVENT_RBUTTONUP) {
		//	if (flag == EVENT_FLAG_ALTKEY) {
				//lasermoving = 0;
				//std::string laser_text = "X0 Y0 F10\n";
				//std::vector<char> chars(laser_text.c_str(), laser_text.c_str() + laser_text.size() + 1u);
				//arduino.writeSerialPort(&chars[0], laser_text.size());
		//	}

		//}
		if (event == EVENT_LBUTTONUP) {
			/*
			if (flag == EVENT_FLAG_CTRLKEY) {
				//laser = Point(x, y);
				cout << "New laser location: " << Point(x, y) << "\n";
			}

			if (flag == EVENT_FLAG_ALTKEY) {
				xintegral = 0;
				yintegral = 0;
				xlaser = (double)(x - laser.x);
				ylaser = (double)(laser.y - y);

				lasermag = sqrt(xlaser*xlaser + ylaser * ylaser);
				laserang = atan2(ylaser, xlaser);
				origlaserang = laserang;
				ylaserinc = laserincmag * sin(laserang);
				xlaserinc = laserincmag * cos(laserang);
				//ylaserinc = laserincmag * sin(ylaser / lasermag);
				//xlaserinc = laserincmag * cos(xlaser / lasermag);
				//if (xlaser < 0) {
				//	xlaserinc = -xlaserinc;
				//}
				xlaserint = 0;
				ylaserint = 0;

				//std::string laser_text = "";
				//cout << x - laser.x << " " << y - laser.y << "\n";
				//laser_text = "X" + std::to_string((x-laser.x)) + " " + "Y" + std::to_string(-(y-laser.y)) + " " + "F10\n";
				//cout << laser_text << "\n";
				//std::vector<char> chars(laser_text.c_str(), laser_text.c_str() + laser_text.size() + 1u);
				//arduino.writeSerialPort(&chars[0], laser_text.size());
				//if (!moving) {
				//	moving = true;
				//}
				//else {
				//	moving = false;
				//}
				//laser = Point(x, y);
				lasermoving = 1;
				cout << "CLICKED!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n";
				//lasermovingcount = 0;
			}
			//if (flag == (EVENT_FLAG_CTRLKEY + EVENT_FLAG_LBUTTON)) {
			//	laser = Point(x, y);
			//}
			*/
			/*
			HWND hwnd = (HWND)cvGetWindowHandle("Microscope rocker");

			if (!IsWindowVisible(hwnd)) {
				cout << "quit" << '\n';
				cv::destroyAllWindows();
				_Exit(0);
			}
			*/
		}
	}
}
/*
void updateCO2() {
	if (co2_sensor.isConnected()) {
		int read_result = co2_sensor.readSerialPort(co2Data + co2_serial_ptr, MAX_DATA_LENGTH - co2_serial_ptr);
		//cout << "Read result " << read_result << "\n";
		co2_serial_ptr = co2_serial_ptr + read_result;
		if (co2_serial_ptr + 100 >= MAX_DATA_LENGTH) {
			co2_serial_ptr = 0;
			co2_read_serial_ptr = 0;
		}

		unsigned int eol = -1;
		unsigned int prev_eol = -1;
		for (unsigned int i = co2_read_serial_ptr; i < co2_serial_ptr; i++) {
			if (co2Data[i] == '\n') {
				prev_eol = eol;
				eol = i;
				//cout << "End of line\n";
			}
		}
		if (prev_eol != -1 && eol != -1) {
			if (1) {//(co2IncomingData[prev_eol + 1] == 'M' && incomingData[prev_eol + 2] == ':') {
				char subbuff[1024];
				//cout << "Got CO2\n";
				memcpy(subbuff, &co2Data[prev_eol + 1], eol - prev_eol - 1);
				subbuff[eol - prev_eol - 1] = '\0';
				//cout << subbuff << "\n";
				char* field;
				field = strtok(subbuff + 2, " ");
				//cout << field << "\n";
				co2 = ((float)stoi(field)) / 1000.0f /3.0*5.0/6.6666;
				log_to_file(false);
			}
		}
	}
	else {
		//cout << "CO2 not connected\n";
	}
}*/
void updateArduino() {

	if (firsttime) {

		socket_zmq.connect("tcp://dlp.local:5555");
		pull_socket.bind("tcp://*:5556");            // Listen for "done"

		// Receiver uses CONFLATE=1 to always get latest frame, so publisher
		// doesn't need aggressive HWM. Default HWM (1000) avoids dropping frames
		// before the IO thread can transmit them.
		image_socket.set(zmq::sockopt::linger, 0);  // Don't wait on close
		image_socket.bind("tcp://*:5557");

		data_socket.set(zmq::sockopt::sndhwm, 1);   // Only buffer 1 data message
		data_socket.set(zmq::sockopt::linger, 0);
		data_socket.bind("tcp://*:5558");

		cmd_socket.bind("tcp://*:5559");

		arduino = new SerialPort(port_name, BAUDRATE);
		if (arduino->isConnected()) cout << "Connection Established" << endl;
		else cout << "ERROR, check port name";
		firsttime = false;
		namedWindow("Microscope");
		setMouseCallback("Microscope", mouse_callback);
		load();
		//cout << "Trying dac\n";
		//dacArduino = new SerialPort(dac_port, BAUDRATE);
		//cout << "got dac\n";
		//if (dacArduino->isConnected()) cout << "DAC Connection Established" << endl;
		//else cout << "ERROR, check DAC port name";

	}
	if (arduino->isConnected()) {
		zmq::message_t reply;
		zmq::recv_result_t result = pull_socket.recv(reply, zmq::recv_flags::dontwait);
		

		if (result) {
			std::string received = reply.to_string();
			std::cout << "Received from Pi: " << received << "\n";
			if (received == "done") {
				cout << "got done\n";
				proj_done = true;
			}
		}
		else {
			// Nothing received this time
		}
		// Drain all pending commands (don't process just one per frame)
		while (true) {
			result = cmd_socket.recv(reply, zmq::recv_flags::dontwait);
			if (!result) break;
			std::string received = reply.to_string();
			parse_command(received);
		}


		//cout << "Connected\n";
		//Check if data has been read or not
		//cout << "Pointers " << serial_ptr << " " << read_serial_ptr << " " << MAX_DATA_LENGTH << "\n";
		int read_result = arduino->readSerialPort(incomingData + serial_ptr, MAX_DATA_LENGTH - serial_ptr);
		//cout << "Read result " << read_result << "\n";
		serial_ptr = serial_ptr + read_result;
		if (serial_ptr + 100 >= MAX_DATA_LENGTH) {
			serial_ptr = 0;
			read_serial_ptr = 0;
		}
		//cout << "Objective: " << objective_offset << "\n";
		unsigned int eol = -1;
		unsigned int prev_eol = -1;
		for (unsigned int i = read_serial_ptr; i < serial_ptr; i++) {
			if (incomingData[i] == '\n') {
				prev_eol = eol;
				eol = i;
			}
		}
		try {
			if (prev_eol != -1 && eol != -1) {
				if (incomingData[prev_eol + 1] == 'M' && incomingData[prev_eol + 2] == ':') {
					char subbuff[1024];
					memcpy(subbuff, &incomingData[prev_eol + 1], eol - prev_eol - 1);
					subbuff[eol - prev_eol - 1] = '\0';
					char* last = strrchr(subbuff, ' ');
					unsigned char checksum = 0;
					unsigned int spaces = 0;
					for (unsigned int i = 0; i < strlen(subbuff); i++) {
						if (subbuff[i] == ' ') {
							spaces += 1;
						}
					}
					//cout << "Spaces: " << spaces << "\n";
					if (spaces == 23) {//Projector
					//if (spaces == 37) {//Imaging
						for (unsigned int i = 0; i < strlen(subbuff) - strlen(last); i++) {
							checksum += subbuff[i];
							//if (subbuff[i] == ' ') {
							//	spaces += 1;
							//}
						}


						//cout << "checksum\n";
						if (((unsigned int)checksum == atoi(last))) {
							//Projector
							char* field;
							field = strtok(subbuff + 2, " ");
							unsigned int field_num = 0;
							for (int m = 0; m < 8; m++) {
								motor_busy[m] = false;
							}
							long focusa_pos = 0;
							long focusb_pos = 0;
							long obja_pos = 0;
							long microc_pos = 0;
							long microa_pos = 0;
							long microb_pos = 0;
							
							while (field != NULL) {

								if (field_num == 0 || field_num == 2 ||
									field_num == 4 || field_num == 6 ||
									field_num == 8 || field_num == 10) {
									unsigned int number = (int)strtol(field, NULL, 16) & 2;
									if (number == 0) {
										motor_busy[field_num / 2] = true;
									}
								}

								if (field_num == 1) {
									focusa_pos = stoi(field);
									motor[0] = stoi(field);
								}
								if (field_num == 3) {
									focusb_pos = stoi(field);
									motor[1] = stoi(field);
								}
								if (field_num == 5) {
									obja_pos = stoi(field);
									motor[2] = stoi(field);
								}
								if (field_num == 7) {
									microc_pos = stoi(field);
									motor[3] = stoi(field);
								}
								if (field_num == 9) {
									microa_pos = stoi(field);
									motor[6] = stoi(field);
								}
								if (field_num == 11) {
									microb_pos = stoi(field);
									motor[7] = stoi(field);
								}
								if (field_num == 12) {
									switches = (int)strtol(field, NULL, 2);
								}
								if (field_num == 13) {
									lightnum = (long)stoi(field, NULL);
								}
								if (field_num == 14) {
									light = (long)stoi(field, NULL);
								}
								if ((field_num > 14) && (field_num <= 22)) {
									motor_busy_num[field_num - 15] = (unsigned char)stoi(field, NULL);
								}
								field = strtok(NULL, " ");
								field_num += 1;
							}
							// Direct conversion - Arduino sends full 32-bit software-tracked positions
							camera_offset_x_driver = -steps_to_mm(microa_pos, 'x');
							camera_offset_y_driver = -steps_to_mm(microc_pos, 'y');
							camera_offset_z_driver = -steps_to_mm(focusa_pos, 'z');
							objective_offset_driver = -steps_to_mm(obja_pos, 'o');

							camera_offset_y = camera_offset_y_driver + camera_offset_y_init;
							camera_offset_x = camera_offset_x_driver + camera_offset_x_init;
							camera_offset_z = camera_offset_z_driver + camera_offset_z_init;
							objective_offset = objective_offset_driver + objective_offset_init;

							

							StringBuffer s;
							Writer<StringBuffer> writer(s);
							writer.StartObject();
							writer.Key("x");
							writer.Double(camera_offset_x);
							writer.Key("y");
							writer.Double(camera_offset_y);
							writer.Key("z");
							writer.Double(camera_offset_z);
							writer.EndObject();
							std::string msg = s.GetString();
							zmq::message_t msg_json(msg.begin(), msg.end());
							data_socket.send(msg_json, zmq::send_flags::dontwait);

							/*
							//Imaging machine
							char* field;
							field = strtok(subbuff + 2, " ");
							unsigned int field_num = 0;
							for (int m = 0; m < 8; m++) {
								motor_busy[m] = false;
							}
							long focusa_pos = 0;
							long focusb_pos = 0;
							long obja_pos = 0;
							long microc_pos = 0;
							long tilta_pos = 0;
							long tiltb_pos = 0;
							long microa_pos = 0;
							long microb_pos = 0;
							float mma1x;
							float mma1y;
							float mma1z;
							float mma2x;
							float mma2y;
							float mma2z;

							while (field != NULL) {
								//cout << field_num << " " << field << "\n";
								//cout << field << " ";

								if (field_num == 0 || field_num == 2 ||
									field_num == 4 || field_num == 6 ||
									field_num == 8 || field_num == 10 ||
									field_num == 12 || field_num == 14) {
									unsigned int number = (int)strtol(field, NULL, 16) & 2;
									if (number == 0) {
										motor_busy[field_num / 2] = true;
									}
								}

								if (field_num == 1) {
									focusa_pos = stoi(field);
									motor[0] = stoi(field);
								}
								if (field_num == 3) {
									focusb_pos = stoi(field);
									motor[1] = stoi(field);
								}
								if (field_num == 5) {
									obja_pos = stoi(field);
									motor[2] = stoi(field);
								}
								if (field_num == 7) {
									microc_pos = stoi(field);
									motor[3] = stoi(field);
								}
								if (field_num == 9) {
									tilta_pos = stoi(field);
									motor[4] = stoi(field);
								}
								if (field_num == 11) {
									tiltb_pos = stoi(field);
									motor[5] = stoi(field);
								}
								if (field_num == 13) {
									microa_pos = stoi(field);
									motor[6] = stoi(field);
								}
								if (field_num == 15) {
									microb_pos = stoi(field);
									motor[7] = stoi(field);
								}

								if (field_num == 16) {
									mma1x = stof(field);
								}
								if (field_num == 17) {
									mma1y = stof(field);
								}
								if (field_num == 18) {
									mma1z = stof(field);
								}
								if (field_num == 19) {
									mma2x = stof(field);
									mma2x = (mma2x + 49.83055699) / 4107.40607844;
								}
								if (field_num == 20) {
									mma2y = stof(field);
									mma2y = (mma2y - 67.52325899) / 4132.21474101;
								}
								if (field_num == 21) {
									mma2z = stof(field);
									mma2z = (mma2z - 40.82501125) / 4107.40607844;
								}


								if (field_num == 22) {
									//rocker_angle[0] = stof(field);
									//back_rocker_angle = stof(field);
								}
								if (field_num == 23) {
									//rocker_angle[1] = stof(field);
									//front_rocker_angle = stof(field);
								}
								if (field_num == 24) {
									//rocker_angle[0] = stof(field);
									back_rocker_noise = stof(field);
								}
								if (field_num == 25) {
									//rocker_angle[1] = stof(field);
									front_rocker_noise = stof(field);
								}
								//if (field_num == 12) {
									//led current
								//}
								//if (field_num >= 13 && field_num < 43) {
								//	small_stepper[field_num - 13] = stoi(field);
								//}
								if (field_num == 26) {
									switches = (int)strtol(field, NULL, 2);
								}
								if (field_num == 27) {
									lightnum = (long)stoi(field, NULL);
								}
								if (field_num == 28) {
									light = (long)stoi(field, NULL);
								}
								if ((field_num > 28) && (field_num <= 36)) {
									motor_busy_num[field_num - 29] = (unsigned char)stoi(field, NULL);
								}
								//if (field_num == 37) {
									//cout << "strlen: " << strlen(field) << " ";
									//for (int i = 0; i < strlen(field); i++) {

									//cout << "wtf";
									//	std::string command_copy(field);
									//	serial_command = command_copy;
									//}
									//serial_command[strlen]
								//}


								field = strtok(NULL, " ");
								field_num += 1;
							}
							//camera_offset_y_driver = (-(steps_to_mm(microa_pos, 'x') + steps_to_mm(microb_pos, 'x')));
							//camera_offset_x_driver = -(steps_to_mm(microa_pos, 'y') - steps_to_mm(microb_pos, 'y'));
							// Direct conversion - Arduino sends full 32-bit software-tracked positions
							camera_offset_x_driver = -steps_to_mm(microa_pos, 'x');
							camera_offset_y_driver = -steps_to_mm(microc_pos, 'y');
							camera_offset_z_driver = -steps_to_mm(focusa_pos, 'z');
							objective_offset_driver = -steps_to_mm(obja_pos, 'o');

							camera_offset_y = camera_offset_y_driver + camera_offset_y_init;
							camera_offset_x = camera_offset_x_driver + camera_offset_x_init;
							camera_offset_z = camera_offset_z_driver + camera_offset_z_init;
							objective_offset = objective_offset_driver + objective_offset_init;
							//focus = steps_to_mm(small_stepper[Z_MOTOR], 'z') + focus_init;
							//focus = steps_to_mm(focusa_pos, 'z') - focus_init;
							
							front_noise[front_noise_ind] = front_rocker_noise;
							front_noise_ind++;
							if (front_noise_ind >= NOISE_MAX) {
								front_noise_ind = 0;
							}
							back_noise[back_noise_ind] = back_rocker_noise;
							back_noise_ind++;
							if (back_noise_ind >= NOISE_MAX) {
								back_noise_ind = 0;
							}
							front_noise_max = 0;
							back_noise_max = 0;
							for (int i = 0; i < NOISE_MAX; i++) {
								if (front_noise[i] > front_noise_max) front_noise_max = front_noise[i];
								if (back_noise[i] > back_noise_max) back_noise_max = back_noise[i];
							}

							


							back_rocker_angle = atan2(sqrt(float(mma1y) * float(mma1y) + float(mma1z) * float(mma1z)), mma1x) * 180 / CV_PI - 90;
							front_rocker_angle = atan2(sqrt(float(mma2y) * float(mma2y) + float(mma2z) * float(mma2z)), mma2x) * 180 / CV_PI - 90;
							back_belt_driver = -steps_to_mm(tilta_pos, 't');
							front_belt_driver = -steps_to_mm(tiltb_pos, 't');
							front_belt = front_belt_driver + front_belt_init;
							back_belt = back_belt_driver + back_belt_init;
							
							*/
							
							/*
							acc_sum[0] += mma1x;
							acc_sum[1] += mma1y;
							acc_sum[2] += mma1z;
							acc_sum[3] += mma2x;
							acc_sum[4] += mma2y;
							acc_sum[5] += mma2z;
							acc_count++;
							if (acc_count >= 100) {
								acc_count = 0;
								for (int i = 0; i < 6; i++) {
									acc_sum[i] /= 100.0;
								}
								cout << "ACC_BACK: " << acc_sum[0] << " " << acc_sum[1] << " " << acc_sum[2] << "\n";
								cout << "BELT_BACK: " << back_belt << "\n";
								cout << "ACC_FRONT: " << acc_sum[3] << " " << acc_sum[4] << " " << acc_sum[5] << "\n";
								cout << "BELT_FRONT: " << front_belt << "\n";
								cout << "\n";

								for (int i = 0; i < 6; i++) {
									acc_sum[i] = 0;
								}
							}*/
							/*
							acc_file << "ACC_BACK: " << mma1x << " " << mma1y << " " << mma1z << "\n";
							acc_file << "BELT_BACK: " << back_belt << "\n";
							acc_file << "ACC_FRONT: " << mma2x << " " << mma2y << " " << mma2z << "\n";
							acc_file << "BELT_FRONT: " << front_belt << "\n";
							
							acc_file << "\n";
							*/
							//cout << "BUSY: ";
							//for (int i = 0; i < 8; i++) {
							//	cout << (int)motor_busy_num[i] << " ";
							//}
							//cout << "\n";
							//cout << front_rocker_angle << " " << back_rocker_angle << " ";
							//for (int i = 0; i < 30; i++) {
							//	cout << small_stepper[i] << " ";
							//}
							//cout << "\n";
							//cout << "Serial command: " << serial_command << "\n";
							//cout << "Checksum: " << checksum << "\n";
							//cout << "\n";
							//cout << "Camera: " << camera_offset_x << " " << camera_offset_y << "\n";
							//cout << "\n" << "Checksum " << (unsigned int)checksum << " " << atoi(last) << "\n";
						}
					}

				}
			}
		}
		catch (exception & err) {
			//chip_roi.copyTo(im2_aligned);
			//cvtColor(detected_edges, detected_edges, COLOR_GRAY2BGR);
			//cvtColor(im2_aligned, im2_aligned, COLOR_GRAY2BGR);
			//im2_aligned = im2_aligned.mul(cv::Scalar(0, 0, 1), 1);
			//addWeighted(im2_aligned, 0.5, image_debug, 0.5, 0.0, image_debug);
			//chip_roi.copyTo(image_debug);
			cout << "Packet messed up\n";
		}
	}

}

class video_display
{
public:


	uint32_t iWidth_;

	int bytesPerPix_;

	uint32_t iHeight_;

	int bitsPerPix_;

	uint8_t* pBuffRGB_ = nullptr;

	uint8_t* pBuffRaw_[MAX_VIDEO_FRAMES] = { nullptr };

	uint32_t buffRawSize_;

	mutable double videoFramesPerSec_ = 0;

	video_display() : iWidth_(0), bytesPerPix_(0), iHeight_(0), bitsPerPix_(0), buffRawSize_(0)
	{
	}

	void set_img_format(uint32_t width, uint32_t height, int bytesPerPix, int bitsPerPix)
	{
		iWidth_ = width;
		iHeight_ = height;
		bytesPerPix_ = bytesPerPix;
		bitsPerPix_ = bitsPerPix;
		pBuffRGB_ = new uint8_t[width * height * 3];

		for (int i = 0; i < MAX_VIDEO_FRAMES; i++) {
			pBuffRaw_[i] = new uint8_t[width * height * bytesPerPix];
		}
		buffRawSize_ = width * height *bytesPerPix;
	}

	void record_video() {
		video_frame = 0;
		recording_video = true;
		std::cout << "Starting video\n";
	}

	

	// Preprocess a grayscale mask through targ + adj transforms and send to Pi via ZMQ.
	// This replicates the same pipeline as update_proj + single-frame illum.
	void send_proj_frame_to_pi(const cv::Mat& mask_gray, double illum_time, int img_cols, int img_rows) const {
		// Stage 1: targ transform (scale, rotate, crop to camera bounds)
		cv::Mat pc1;
		cvtColor(mask_gray, pc1, COLOR_GRAY2BGR);
		cv::resize(pc1, pc1, cv::Size(mask_gray.cols * proj_targ_sx, mask_gray.rows * proj_targ_sy), cv::INTER_LINEAR);
		cv::Point2f center1(pc1.cols / 2., pc1.rows / 2.);
		cv::Mat rot1 = cv::getRotationMatrix2D(center1, proj_targ_r, 1.0);
		cv::warpAffine(pc1, pc1, rot1, pc1.size());
		int start_x = max(proj_targ_x, 10);
		int start_y = max(proj_targ_y, 10);
		int end_x = img_cols - 10;
		int end_y = img_rows - 10;
		Rect targ_roi(start_x - proj_targ_x, start_y - proj_targ_y, end_x - start_x, end_y - start_y);
		cv::Mat p_sub = pc1(targ_roi);

		// Stage 2: adj transform (scale, rotate, paste into 1440x2560)
		cv::Mat vclone = p_sub.clone();
		cv::Mat voutput(1440, 2560, CV_8UC3, cv::Scalar(0, 0, 0));
		cv::resize(vclone, vclone, cv::Size(p_sub.cols * proj_adj_sx, p_sub.rows * proj_adj_sy), cv::INTER_LINEAR);
		cv::Point2f center2(vclone.cols / 2., vclone.rows / 2.);
		cv::Mat rot2 = cv::getRotationMatrix2D(center2, proj_adj_r, 1.0);
		cv::warpAffine(vclone, vclone, rot2, vclone.size());
		int sx = max(proj_adj_x, 0);
		int sy = max(proj_adj_y, 0);
		int ex = min(proj_adj_x + vclone.cols, voutput.cols);
		int ey = min(proj_adj_y + vclone.rows, voutput.rows);
		Rect v_out_roi(sx, sy, ex - sx, ey - sy);
		Rect v_src_roi(sx - proj_adj_x, sy - proj_adj_y, ex - sx, ey - sy);
		vclone(v_src_roi).copyTo(voutput(v_out_roi));

		// JPEG encode and send via ZMQ multipart
		StringBuffer vs;
		Writer<StringBuffer> vwriter(vs);
		vwriter.StartObject();
		vwriter.Key("image"); vwriter.Bool(true);
		vwriter.Key("action"); vwriter.String("illum");
		vwriter.Key("proj_time"); vwriter.Double(illum_time);
		vwriter.EndObject();
		std::string vmsg = vs.GetString();
		zmq::message_t vmsg_json(vmsg.begin(), vmsg.end());
		socket_zmq.send(vmsg_json, zmq::send_flags::sndmore);
		std::vector<uchar> jpg_buf;
		std::vector<int> enc = { cv::IMWRITE_JPEG_QUALITY, 60 };
		cv::imencode(".jpg", voutput, jpg_buf, enc);
		zmq::message_t img_msg(jpg_buf.data(), jpg_buf.size());
		socket_zmq.send(img_msg, zmq::send_flags::dontwait);
	}

	void display_blocking(uint8_t *p_rawImage, uint32_t buffLength) const
	{
		
		//mesaure this function interval.
		static auto nbFrames = 0;
		static auto t = static_cast<double>(cv::getTickCount());

		nbFrames++;
		double elapsedTimeMs = ((static_cast<double>(cv::getTickCount()) - t) / cv::getTickFrequency()) * 1000;
		if (elapsedTimeMs >= 1000)
		{
			videoFramesPerSec_ = elapsedTimeMs / static_cast<double>(nbFrames);
			nbFrames = 0;
			t = static_cast<double>(cv::getTickCount());
		}



		memcpy(pBuffRaw_[video_frame], p_rawImage, buffLength);

		////test display from this thread.
		//util_image::gammaCorrection(rawBuff, rawBuff, 1280, 720, 12, 1.6);

		util_image::raw_to_rgb(pBuffRaw_[video_frame], 0, pBuffRGB_, 0, iWidth_*iHeight_, bitsPerPix_);

		cv::Mat image(iHeight_, iWidth_, CV_8UC3, pBuffRGB_);
		cv::flip(image, image, 0);
		
		//cvtColor(image, image, COLOR_GRAY2BGR);
		
		//image_debug = image.clone();
		
		//cv::Mat image(1280, 960, CV_8UC3);
		if (recording_video) {
			chrono_times[video_frame] = std::chrono::high_resolution_clock::now();
			video_frame++;
		}
		frame_count++;
		//int motor_busy[5] = { 0 };
		
		if (frame_count == 2) { 
			//cout << "Arduino " << arduino_num << "\n";
			arduino_num += 1;
			//for (int mot = 0; mot < 8; mot++) {
			//	std::cout << motor_busy[mot] << " ";
			//}
			//std::cout << "\n";
			updateArduino();
			//updateCO2();
			//button_mode = -1;

			//cout << (switches & 0b10000) << " " << (switches & 0b01000) << " " << 
			//	(switches & 0b00100) << " " << (switches & 0b00010)  << " " << (switches & 0b00001)  << "\n";
			//cout << (switches & 0b00100) << "\n";
			
			if ((switches | 0b000001) != 63) {
				double elapsedTime = ((static_cast<double>(cv::getTickCount()) - double_click_time) / cv::getTickFrequency());
				if (double_click_count == 0) {
					double_click_count = 1;
					double_click_time = static_cast<double>(cv::getTickCount());
				}
				if ((double_click_count == 2) && (elapsedTime>0.1) && (elapsedTime < 2.0)) {
					double_click_count = 3;
					double_click_time = static_cast<double>(cv::getTickCount());
				}
				if (elapsedTime > 2.0) {
					double_click_count = 0;
				}				
			}
			else {
				double elapsedTime = ((static_cast<double>(cv::getTickCount()) - double_click_time) / cv::getTickFrequency());
				if ((double_click_count == 1) && (elapsedTime > 0.1) && (elapsedTime < 2.0)) {
					double_click_count = 2;
					double_click_time = static_cast<double>(cv::getTickCount());
				}
				if ((double_click_count == 3) && (elapsedTime > 0.1) && (elapsedTime < 2.0)) {
					double_click_count = 0;
					if (button_mode == 0 || button_mode == 15) {
						button_mode = -1;
					}
					if (button_mode == -6) {
						button_mode = 1;
					}
				}
				if (elapsedTime > 2.0) {
					double_click_count = 0;
				}
			}
			//if (switches)
			//if (switches != 0b11111)
			//if ((switches & 0b01000) == 0) {
			//	pause_machine();
			//}
			bool next_auto = false;
			if (automating) {
				if (automate_ind >= (automate.size())) {
					automating = false;
					auto_text = "DONE";
					next_auto = false;
					cout << automate_ind << " done???\n";
				}
				else {
					next_command = automate[automate_ind];
				}
			}
			if (automating) {
				
				
				if (program_paused==1) {
					
				}
				else {
					if (program_paused == 2) {
						program_paused = 1;
					}
					if ((cond == 1) && (center_fail == false)) {
						next_auto = true;	
					}
					if (auto_delay_type.substr(0, 5) == "CLOCK") {
						time_t now = time(0);
						//char* time_str = "21:47";
						//int hh, mm;
						struct tm time_thresh_tmp;
						time_thresh_tmp = *localtime(&now);
						//sscanf(time_str.c_str(), "%d:%d", &hh, &mm);
						time_thresh_tmp.tm_hour = time_thresh.tm_hour;
						time_thresh_tmp.tm_min = time_thresh.tm_min;
						time_thresh_tmp.tm_sec = 0;
						
						time_t thresh_t = mktime(&time_thresh_tmp);
						double time_diff = difftime(now, thresh_t);
						cout << "Time diff: " << time_diff << "\n";
						if ((time_diff >= 0) && (time_diff < 300)) {
							next_auto = true;
						}
						
						//printf("%f\n", difftime(now, thresh_t));
						//time_t now = time(0);

						//char* time_str = "21:47";
						//int hh, mm;
						//struct tm time_thresh;
						//time_thresh = *localtime(&now);
						//sscanf(time_str, "%d:%d", &hh, &mm);
						//time_thresh.tm_hour = hh;
						//time_thresh.tm_min = mm;
						//time_thresh.tm_sec = 0;
						//time_t thresh_t = mktime(&time_thresh);

						//printf("%f\n", difftime(now, thresh_t));

						//struct tm time = { 0 };
						//time_t now = time(0);
						//struct tm tstruct;
						//char buf[80];
						//tstruct = *localtime(&now);
						//strftime(buf, sizeof(buf), "%Y-%m-%d-%H-%M-%S", &tstruct);
						//std::string time_str(buf);

						//double elapsedTime = ((static_cast<double>(cv::getTickCount()) - prev_automate_time) / cv::getTickFrequency());
						//if (elapsedTime > automate_delay) {
						//	next_auto = true;
						//}
					}
					else if (auto_delay_type.substr(0, 5) == "SLEEP") {
						double elapsedTime = ((static_cast<double>(cv::getTickCount()) - prev_automate_time) / cv::getTickFrequency());
						if (elapsedTime > automate_delay) {
							next_auto = true;
						}
					}
					else if (auto_delay_type.substr(0, 5) == "ILLUM") {
						if (proj_done) {
							cout << "Projector Done\n";
							proj_done = false;
							next_auto = true;
						}
					}
					else if (auto_delay_type.substr(0, 5) == "IMAGE") {
						if (!running) {
							cout << "NEXT!!!\n";
							next_auto = true;
						}
					}
					else if (auto_delay_type.substr(0, 5) == "MOTOR") {
						if (!motorBusy(stoi(auto_delay_type.substr(5)))) {
							cout << "Motor done\n";
							next_auto = true;
						}
						//int motor_busy_sum = motor_busy[0] + motor_busy[1] + motor_busy[2] + motor_busy[3]
						//	+ motor_busy[4] + motor_busy[5] + motor_busy[6] + motor_busy[7];
						//if (motor_busy_mode == 0 && motor_busy_sum != 0) {
						//	motor_busy_mode = 1;
						//}
						//else if (motor_busy_mode == 1 && motor_busy_sum == 0) {
						//	cout << "NEXT!!!\n";
						//	next_auto = true;
						//	motor_busy_mode = 0;
						//}
					}
					else if (auto_delay_type.substr(0, 5) == "FROCK") {
						if (small_stepper[FRONT_ROCKER_HOLD] == 0) {

							cout << "NEXT!!!\n";
							next_auto = true;
						}
					}
					else if (auto_delay_type.substr(0, 5) == "BROCK") {
						if (small_stepper[BACK_ROCKER_HOLD] == 0) {

							cout << "NEXT!!!\n";
							next_auto = true;
						}
					}
					/*
					else if (auto_delay_type.substr(0, 5) == "MOTOR") {

						cout << "MOTOR BUSY: " << stoi(auto_delay_type.substr(5)) << "\n";
						if (motor_busy[stoi(auto_delay_type.substr(5))] == 2) {
							next_auto = true;
						}
					}*/

				}
				
				
				
				if (next_auto) {
					cout << "NEXT AUTO???\n";
					//auto_text = automate.front();
					auto_text = automate[automate_ind];
					last_command = automate[automate_ind];

					automate_ind++;
					
					auto_text.erase(std::remove(auto_text.begin(), auto_text.end(), '\n'),
						auto_text.end());
					auto_text.erase(std::remove(auto_text.begin(), auto_text.end(), '\r'),
						auto_text.end());
					//automate.pop();
					vector <string> tokens;
					// stringstream class check1 
					stringstream check1(auto_text);
					string intermediate;
					// Tokenizing w.r.t. space ' ' 
					while (getline(check1, intermediate, ','))
					{
						tokens.push_back(intermediate);
					}
					if (tokens.size() > 0) {
						auto_text = tokens[0];
						if (auto_text[0] != '#') {
							if (tokens.size() == 2) {
								auto_delay_type = tokens[1];
								//auto_text = automate[automate_ind];// .split(',')[0];
								//cout << "auto_text: " << auto_text << "\n";
								//cout << "auto_delay_type: " << auto_delay_type << "\n";
								//auto_delay_type = automate[automate_ind].split(',')[1];
								if (auto_delay_type.substr(0, 5) == "SLEEP") {
									automate_delay = stoi(auto_delay_type.substr(5));
									//cout << "got delay\n";
								}
								if (auto_delay_type.substr(0, 5) == "CLOCK") {
									string time_str = auto_delay_type.substr(5);
									cout << "Time str: " << time_str << "\n";
									time_t now = time(0);
									//char* time_str = "21:47";
									int hh, mm;
									//struct tm time_thresh;
									time_thresh = *localtime(&now);
									sscanf(time_str.c_str(), "%d:%d", &hh, &mm);
									time_thresh.tm_hour = hh;
									time_thresh.tm_min = mm;
									time_thresh.tm_sec = 0;
									time_t thresh_t = mktime(&time_thresh);

									printf("wtf %f\n", difftime(now, thresh_t));

								}
								cout << "automate_delay: " << automate_delay << "\n";
								//if (auto_delay_type.substr(5) == "MOTOR") {
									//motor_busy = [0, 0, 0, 0, 0];
								//}
								//automate_ind += 1;
								prev_automate_time = static_cast<double>(cv::getTickCount());
							}
							
							cout << "AUTO " << auto_count << ": " << auto_text << "\n";
							
							time_t my_time = time(NULL);
							//cout << ctime(&my_time) << "\n";
							if ((auto_text == "LOOP") || (auto_text == "REPORT")) {
								string message = "Finished automation loop\n";
								cout << message;
								//system("start powershell.exe Set-ExecutionPolicy RemoteSigned \n");
								////system("start powershell.exe C:\\Users\\themachine_desktop\\Documents\\alarm.ps1");
								//system("start powershell.exe D:\\themachine\\loop.ps1");
								cout << "Timed out: " << timedout << "\n";
								if (auto_text == "LOOP") {
									//cout << automate.size() << "\n";
									//cout << automate_loop.size() << "\n";
									//while (!automate.empty()) {
									//	automate.pop();
									//}
									//automate = automate_loop;
									//cout << automate.size() << "\n";
									automate_ind = 0;
									automating = true;
								}
								else {
									automating = false;
								}
								//auto_text = "";

								//message = message + "Temperature: " + chamber_temperature_str + "\\n";
								//message = message + "CO2: " + co2_str + "\\n";
								//message = message + "Humidity: " + humidity_str + "\\n";
								//os.system('echo "' + message + '" | mail -aFrom:the.machine@mssm.edu -s "Loop" david.sachs@mssm.edu');
							}
							 else {
								{
									if (0) {//(auto_text[0] == 'L' && auto_text[1] == 'L') {
										cout << "Laser intercept\n";
									}
									else {
										
										
											parse_command(auto_text);
										
									}
								}
							}
						}
					}
					auto_count++;
				}
			}
			frame_count = 0;
			fps = 1 / videoFramesPerSec_ * 1000;
			std::string fps_str = "FPS: " + std::to_string(fps);
			//std::cout << str << "\n";
			//std::cout << "co2 " << co2 << "\n";
			//cvtColor(image, image, COLOR_BGR2GRAY);
			
			double focus_test = 0;
			if (0) {//((!firstimage) && (run_flow)) {
				
				const int MAX_CORNERS = 500;
				vector< cv::Point2f > cornersA, cornersB;
				int win_size = 10;
				cv::goodFeaturesToTrack(
					image,                         // Image to track
					cornersA,                     // Vector of detected corners (output)
					MAX_CORNERS,                  // Keep up to this many corners
					0.01,                         // Quality level (percent of maximum)
					5,                            // Min distance between corners
					cv::noArray(),                // Mask
					3,                            // Block size
					false,                        // true: Harris, false: Shi-Tomasi
					0.04                          // method specific parameter
				);

				cv::cornerSubPix(
					image,                           // Input image
					cornersA,                       // Vector of corners (input and output)
					cv::Size(win_size, win_size),   // Half side length of search window
					cv::Size(-1, -1),               // Half side length of dead zone (-1=none)
					cv::TermCriteria(
						cv::TermCriteria::MAX_ITER | cv::TermCriteria::EPS,
						20,                         // Maximum number of iterations
						0.03                        // Minimum change per iteration
					)
				);

				// Call the Lucas Kanade algorithm
				//
				vector<uchar> features_found;
				cv::calcOpticalFlowPyrLK(
					image,                         // Previous image
					prev_image,                         // Next image
					cornersA,                     // Previous set of corners (from imgA)
					cornersB,                     // Next set of corners (from imgB)
					features_found,               // Output vector, each is 1 for tracked
					cv::noArray(),                // Output vector, lists errors (optional)
					cv::Size(win_size * 2 + 1, win_size * 2 + 1),  // Search window size
					5,                            // Maximum pyramid level to construct
					cv::TermCriteria(
						cv::TermCriteria::MAX_ITER | cv::TermCriteria::EPS,
						20,                         // Maximum number of iterations
						0.3                         // Minimum change per iteration
					)
				);
				
				double xtot = 0;
				double ytot = 0;
				long flowcount = 0;
				for (int i = 0; i < static_cast<int>(cornersA.size()); ++i) {
					if (!features_found[i]) {
						continue;
					}
					line(
						image_debug,                        // Draw onto this image
						cornersA[i],                 // Starting here
						cornersB[i],                 // Ending here
						cv::Scalar(0, 255, 0),       // This color
						1,                           // This many pixels wide
						cv::LINE_AA                  // Draw line in this style
					);
					flowcount++;
					xtot += cornersB[i].x - cornersA[i].x;
					ytot += cornersB[i].y - cornersA[i].y;
				}

				/*
				for (int y = 0; y < flow.rows; y += 1) {
					for (int x = 0; x < flow.cols; x += 1)
					{
						// get the flow from y, x position * 3 for better visibility
						const Point2f flowatxy = flow.at<Point2f>(y, x) * 1;
						xtot = xtot + (double)flowatxy.x;
						ytot = ytot + (double)flowatxy.y;
						flowcount++;
						// draw line at flow direction
						//line(img2, Point(x, y), Point(cvRound(x + flowatxy.x), cvRound(y + flowatxy.y)), Scalar(255, 0, 0));
						// draw initial point
						//circle(img2, Point(x, y), 1, Scalar(0, 0, 0), -1);
					}
				}
				*/
				flowmag = sqrt((xtot / flowcount)*(xtot / flowcount) + (ytot / flowcount)*(ytot / flowcount));
				flowang = -atan2(ytot, xtot);
				//cout << "Mag flow" << " " << sqrt((xtot / flowcount)*(xtot / flowcount) + (ytot / flowcount)*(ytot / flowcount)) << "\n";


				xintegral = xintegral + xtot / flowcount;
				yintegral = yintegral + ytot / flowcount;
				integralang = -atan2(yintegral, xintegral);
				//if (lasermoving != 0) moveLaser();
				//cout << "Total flow: " << xintegral << " " << yintegral << "\n";

			}
			else {
				firstimage = false;
				//if (lasermoving != 0) moveLaser();
			}
			prev_image = image.clone();
			//if (!image_debug.empty()) {
			//	image = .clone();
			//}
			vector<Vec4i> lines;
			vector<Vec3f> circles;
			
			if (run_hough_circles || run_hough_lines || run_map || run_focus) {
				Mat src, src_gray;
				Mat dst;
				//cout << run_hough_circles << run_hough_lines << run_map  << run_focus << "\n";
				/// Reduce noise with a kernel 3x3
				//blur(image, detected_edges, Size(30, 30));

				/// Canny detector
				//int wtf = 0; 
				//int edgeThresh = 1;
				int lowThreshold = 400;// 400;// 200;//100
				int lowThresholdFocus = 800;// 1600;
				//int const max_lowThreshold = 100;
				int ratio = 2;
				int kernel_size = 5;
				pyrDown(image, detected_edges, Size(image.cols / 2, image.rows / 2));
				
				//if (image_mode == IMAGE_OPENCV) {
					
				//}
				cvtColor(detected_edges, detected_edges_tmp, COLOR_BGR2GRAY);
				//threshold_image = detected_edges.clone();
				//f (image_mode = IMAGE_MICRO_OPENCV) {
				//	pyrDown(image, image_debug, Size(image.cols / 2, image.rows / 2));
				//}
				//detected_edges.copyTo(image);
				//pyrDown(image, detected_edges, Size(image.cols / 2, image.rows / 2));
				vector<vector<Point> > contours;
				vector<Vec4i> hierarchy;
				Canny(detected_edges_tmp, detected_edges, lowThreshold, lowThreshold* ratio, kernel_size);
				Canny(detected_edges_tmp, detected_edges_focus, lowThresholdFocus, lowThresholdFocus* ratio, kernel_size);
				//cv::threshold(threshold_image, threshold_image, 0, 255, CV_THRESH_BINARY | CV_THRESH_OTSU);
				//Canny(threshold_image, threshold_image, lowThreshold, lowThreshold*ratio, kernel_size);


				//findContours(detected_edges, contours, hierarchy, RETR_TREE, CHAIN_APPROX_SIMPLE);

				image_debug = detected_edges_focus.clone();
				
				
				//addWeighted(image_debug, 1.0, threshold_image, 0.0, 0.0, image_debug);
				cvtColor(image_debug, image_debug, COLOR_GRAY2BGR);
				/*
				RNG rng(12345);
				vector<Rect> boundRect(contours.size());
				contoured_edges = Mat::zeros(detected_edges.rows, detected_edges.cols, CV_8UC1);
				//image_debug = Mat::zeros(image_debug.rows, image_debug.cols, CV_8UC3);
				for (size_t i = 0; i < contours.size(); i++)
				{
					//cout << "Arc length: " << arcLength(contours[i], false);
					boundRect[i] = boundingRect(contours[i]);
					//double contour_length = arcLength(contours[i], false);
					double max_length = boundRect[i].height;
					if (boundRect[i].width > max_length) {
						max_length = boundRect[i].width;
					}
					
					if (max_length > 50) {
						//double bound_area = boundRect[i].height * boundRect[i].width;

						//cout << "Area/length: " << bound_area/max_length << "\n";
						//if ((bound_area/max_length) < 100) {
					//if (arcLength(contours[i], false) > 100) {
						//if ((contour_area / contour_length) < 0.1) {
							//cout << contour_area / contour_length << "\n";	
							Scalar color = Scalar(rng.uniform(0, 256), rng.uniform(0, 256), rng.uniform(0, 256));
							
							drawContours(contoured_edges, contours, (int)i, Scalar(255, 255, 255), 1, LINE_8, hierarchy, 0);
							//drawContours(image_debug, contours, (int)i, Scalar(255, 255, 255), 1, LINE_8, hierarchy, 0);
							drawContours(image_debug, contours, (int)i, color, 2, LINE_8, hierarchy, 0);
						//}
					}
				}*/
				//MatIterator_<uchar> it, end;
				//unsigned long int sum = 0;
				//for (it = detected_edges.begin<uchar>(), end = detected_edges.end<uchar>(); it != end; ++it)
				//{
				//	sum = *it != 0;
				//}
				//focus_test = (double)sum / (detected_edges.cols * detected_edges.rows);
				//cout << "Focus rate " << countNonZero(detected_edges) << "\n";
				
				if (run_hough_lines) {
					//HoughLines(detected_edges, lines, 1, CV_PI / 180, 150, 0, 0); // runs the actual detection
					HoughLinesP(detected_edges, lines, 1, CV_PI / 180, 80, 30, 10);

				}

				if (run_focus) {

					double focus_min, focus_max;
					minMaxLoc(image, &focus_min, &focus_max);
					cout << "Focus mode " << focus_mode << "\n";
					double elapsedTime = ((static_cast<double>(cv::getTickCount()) - prev_focus_time) / cv::getTickFrequency());
					string focus_cmd = "Z";
					if (elapsedTime > 10) {
						
						cout << "Focus timed out\n";
						timedout += 1;
						image_attempts += 1;
						if (image_attempts >= 3) {
							focus_mode = 5;
						}
						else { 
							focus_mode = 1;
							focus_cmd = "Z0.5\n";
							parse_command(focus_cmd);
							prev_focus_time = static_cast<double>(cv::getTickCount());
						}
					}
					else if ((focus_mode == 1) && (!motorBusy(0)) && (!motorBusy(1))) {
						cout << "FOCUS START\n";
						string final_text = "F200 I2\n";
						std::vector<char> chars(final_text.c_str(), final_text.c_str() + final_text.size() + 1u);
						bool serialerror = arduino->writeSerialPort(&chars[0], final_text.size());
						focus_mode = 2;
						//prev_light_time = static_cast<double>(cv::getTickCount());
						//parse_command("II1\n");
					}
					else if (focus_mode == 2) {
						cout << focus_max << " " << prev_focus_max << "\n";
						if ((focus_max * 1.5) < prev_focus_max) {
							focus_mode = 3;
						}
					}
					else if (focus_mode == 3) {
						if ((prev_focus_max * 1.5) < focus_max) {
							focus_mode = 4;
							focus_level = 0;
						}
					}
					if (focus_mode==4) {
						if ((focus_max * 1.5) < prev_focus_max) {
							focus_mode = 5;
						}
						else {
							if (focus_level < 500) {
								float line_av = 0;
								int line_num = 0;
								
								for (size_t i = 0; i < lines.size(); i++) {
									Point p1, p2;
									p1 = Point(lines[i][0], lines[i][1]);
									p2 = Point(lines[i][2], lines[i][3]);
									//calculate angle in radian,  if you need it in degrees just do angle * 180 / PI
									float length = sqrt((p1.y - p2.y) * (p1.y - p2.y) + (p1.x - p2.x) * (p1.x - p2.x));
									float angle = atan2(p1.y - p2.y, p1.x - p2.x) * 180 / 3.1415962;
									bool more_line = false;
									float line_dir = fabs(90.0 - fabs(angle));
									cout << "orientation: " << orientations[current_chip] << " " << TAB_RIGHT << "\n";
									cout << "orientation: " << round(orientations[current_chip]) << " " << round(TAB_RIGHT) << "\n";
									if ((round(orientations[current_chip])==round(TAB_LEFT)) || (round(orientations[current_chip]) == round(TAB_RIGHT))) {
										line_dir = fabs(180 - fabs(angle));
										cout << "HORIZONTAL\n";
									}
									else {
										cout << "VERTICAL\n";
									}
									cout << "line_dir " << line_dir << " " << angle << "\n";
									line_av += line_dir;
									line_num += 1;
									cout << length << " " << angle << " " << line_dir << "\n";
								}
								focus_line[focus_level] = 100;
								if (line_num > 5) {
									focus_line[focus_level] = line_av / line_num;
									cout << line_av / line_num << " " << line_num << "\n";
								}

								focus_edges[focus_level] = countNonZero(detected_edges_focus);
								focus_motor[focus_level] = camera_offset_z;


								focus_level++;
							}
						}
					}
					else if ((focus_mode == 5) && (!motorBusy(0) && !motorBusy(1))
						&& (fabs(focus_motor[0] - camera_offset_z)<0.2) ) {
						cout << "Done focus\n";
						cout << focus_motor[0] << " " << camera_offset_z << " " << fabs(focus_motor[0] - camera_offset_z) << "\n";
						focus_mode = 0;
						run_focus = false;
						running = false;
						int max_focus_level = 0;
						int max_focus = 0;
						
						for (int i = 0; i < focus_level; i++) {
							
							if ((focus_edges[i] > max_focus) && (focus_line[i]<30)) {
								max_focus = focus_edges[i];
								max_focus_level = i;
							}
							cout << i << " " << focus_line[i] << " " << focus_motor[i] << " " << focus_edges[i] << " " << max_focus << " " << max_focus_level << "\n";
						}
						//cout << "\n";
						
						run_focus = false;
						running = false;
						
						if (max_focus < 10) {
							cout << "Focus failed\n";
							focus_cmd = "Z0.5\n";
						}
						else {

							focus_cmd = focus_cmd + std::to_string((((double)max_focus_level) / focus_level) * 1.0) + "\n";
						}
						cout << "FOCUS: " << focus_cmd << "\n";
						parse_command(focus_cmd);
						focus_level = 0;
						image_attempts = 0;
					}
					prev_focus_max = focus_max;
				}
				if (0) {//(run_focus) {
					//double elapsedTime = ((static_cast<double>(cv::getTickCount()) - prev_focus_time) / cv::getTickFrequency());
					//if ((elapsedTime > focus_delay)) {// && (small_stepper[Z_MOTOR_STEPS]==0)) {
					if ((!motorBusy(0)) && (!motorBusy(1))) {
						//prev_focus_time = static_cast<double>(cv::getTickCount());

						if (focus_level < 16) {
							focus_levels[focus_level] = countNonZero(detected_edges);
							parse_command("Z0.025\n");
							//focus_delay = 2.0;
						}
						else if (focus_level == 16) {
							parse_command("Z-0.4\n");
							//focus_delay = 9;
						}
						else if (focus_level == 17) {
							int max_focus_level = 0;
							int max_focus = 0;
							for (int i = 0; i < 16; i++) {
								//cout << focus_levels[i] << " ";
 								if (focus_levels[i] > max_focus) {
									max_focus = focus_levels[i];
									max_focus_level = i;
								}
							}
							//cout << "\n";
							run_focus = false;
							running = false;
							string focus_cmd = "Z";
							focus_cmd = focus_cmd + std::to_string(max_focus_level*0.025) + "\n";
							cout << "FOCUS: " << focus_cmd << "\n";
							parse_command(focus_cmd);
						}
						focus_level++;	
					}
				}
			}
			Mat resized_chip, chip_roi, im2_aligned;
			
			bool got_map = false;
			//cout << "chip " << chip_feedback_x << " " << chip_feedback_y << "\n";
			// Set a 2x3 or 3x3 warp matrix depending on the motion model.
			Mat warp_matrix;
			if (run_map) {

				//resize(chip, resized_chip, cv::Size(), 19.0, 19.0, cv::INTER_CUBIC);
				resize(chip, resized_chip, cv::Size(), 21.0 / 2, 21.0 / 2, cv::INTER_CUBIC);
				//Draw chip


				//cvtColor(chip, chip, COLOR_BGR2GRAY);
				//cvtColor(chip, chip, COLOR_GRAY2BGR);
				// Setup a rectangle to define your region of interest
				//MatRect(0, 0, detected_edges.rows, detected_edges.cols));
				//Mat croppedImage;
				//ROI.copyTo(croppedImage);

				//cv::Rect myROI = cv::Rect(2850/2+chip_feedback_x, 5070/2+chip_feedback_y, detected_edges.cols, detected_edges.rows);
				//cv::Rect myROI = cv::Rect(1425 + chip_pos_x + chip_feedback_x, 2535 + chip_pos_y + chip_feedback_y, detected_edges.cols, detected_edges.rows);
				cv::Rect myROI = cv::Rect(resized_chip.cols / 2 - detected_edges.cols / 2 + chip_pos_x + chip_feedback_x,
					635 + resized_chip.rows / 2 - detected_edges.rows / 2 + chip_pos_y + chip_feedback_y, detected_edges.cols, detected_edges.rows);
				chip_roi = resized_chip(myROI);
				bitwise_not(chip_roi, chip_roi);
				//cout << "Rect " << resized_chip(myROI).size() << "\n";
				//cout << "Chip " << chip.size() << "\n";
				//cout << "Edges " << detected_edges.size() << "\n";
				//cv::Mat croppedChip = chip(myROI);
				//Mat chip(detected_edges.rows, detected_edges.cols, CV_8UC3, Scalar(0, 0, 0));
				//drawChip(chip);
				//Point pt1, pt2;
				//pt1.x = 0;
				//pt1.y = 0;
				//pt2.x = 50;
				//pt2.y = 50;
				//line(chip, pt1, pt2, Scalar(0, 0, 255), 3, LINE_AA);
				cvtColor(chip_roi, chip_roi, COLOR_BGR2GRAY);

				//croppedChip.copyTo(detected_edges);
				//addWeighted(resized_chip(myROI), 0.5, detected_edges, 0.5, 0.0, detected_edges);

				// Define the motion model
				const int warp_mode = MOTION_TRANSLATION;

				

				// Initialize the matrix to identity
				if (warp_mode == MOTION_HOMOGRAPHY)
					warp_matrix = Mat::eye(3, 3, CV_32F);
				else
					warp_matrix = Mat::eye(2, 3, CV_32F);

				// Specify the number of iterations.
				int number_of_iterations = 10;

				// Specify the threshold of the increment
				// in the correlation coefficient between two iterations
				double termination_eps = 1e-10;

				// Define termination criteria
				TermCriteria criteria(TermCriteria::COUNT + TermCriteria::EPS, number_of_iterations, termination_eps);
				
				// Standard Hough Line Transform
				//vector<Vec2f> lines; // will hold the results of the detection

				// Run the ECC algorithm. The results are stored in warp_matrix.
				if (!motor_busy[0]) {//1) {
					//cout << "Motor busy " << motor_busy << "\n";
					try {
						if (move_mode != MOVE_REF) {
							findTransformECC(
								detected_edges,
								chip_roi,
								warp_matrix,
								warp_mode,
								criteria
							);

							if (warp_mode != MOTION_HOMOGRAPHY)
								// Use warpAffine for Translation, Euclidean and Affine
								warpAffine(chip_roi, im2_aligned, warp_matrix, detected_edges.size(), INTER_LINEAR + WARP_INVERSE_MAP);
							else
								// Use warpPerspective for Homography
								warpPerspective(chip_roi, im2_aligned, warp_matrix, detected_edges.size(), INTER_LINEAR + WARP_INVERSE_MAP);
							//const double* Mi = warp_matrix.ptr<double>;
							/*
							cout << "Matrix: " <<
								//warp_matrix.at<float>(0, 0) << " " <<
								//warp_matrix.at<float>(0, 1) << " " <<
								warp_matrix.at<float>(0, 2) << " " <<
								//warp_matrix.at<float>(1, 0) << " " <<
								//warp_matrix.at<float>(1, 1) << " " <<
								warp_matrix.at<float>(1, 2) << " " <<
								//warp_matrix.at<float>(2, 0) << " " <<
								//warp_matrix.at<float>(2, 1) << " " <<
								//warp_matrix.at<float>(2, 2) <<
								"\n";
								*/
							got_map = true;
							// if (fabs(chip_pos_x + chip_feedback_x) < 450) {
								//chip_feedback_x += warp_matrix.at<float>(0, 2);
							//}
							//chip_feedback_y += warp_matrix.at<float>(1, 2);
							//cout << "Chip: " << chip_feedback_x + chip_pos_x << " " << chip_feedback_y + chip_pos_y << "\n";
						}
						else {
							//chip_roi.copyTo(im2_aligned);
							got_map = true;
						}

					}
					catch (exception &err) {
						//chip_roi.copyTo(im2_aligned);
						//cvtColor(detected_edges, detected_edges, COLOR_GRAY2BGR);
						//cvtColor(im2_aligned, im2_aligned, COLOR_GRAY2BGR);
						//im2_aligned = im2_aligned.mul(cv::Scalar(0, 0, 1), 1);
						//addWeighted(im2_aligned, 0.5, image_debug, 0.5, 0.0, image_debug);
						//chip_roi.copyTo(image_debug);
						cout << "Alignment failed\n";
					}
					/*
					if (got_map) {
							cvtColor(detected_edges, detected_edges, COLOR_GRAY2BGR);
							cvtColor(im2_aligned, im2_aligned, COLOR_GRAY2BGR);

							//cout << "Matrix: " << Mi[0] << " " << Mi[1] << " " << Mi[2] << " " << Mi[3] << "\n";
							//cout << "Matrix: " << warp_matrix.col(2).data << "\n";
							chip_feedback_x += warp_matrix.at<float>(0, 2);
							chip_feedback_y += warp_matrix.at<float>(1, 2);
							//chip_roi.copyTo(im2_aligned);
							im2_aligned = im2_aligned.mul(cv::Scalar(0, 1, 0), 1);
							addWeighted(im2_aligned, 0.5, detected_edges, 0.5, 0.0, detected_edges);
						}
						else {
							//chip_feedback_x = 0;
							//chip_feedback_y = 0;
							chip_roi.copyTo(im2_aligned);
							cvtColor(detected_edges, detected_edges, COLOR_GRAY2BGR);
							cvtColor(im2_aligned, im2_aligned, COLOR_GRAY2BGR);
							im2_aligned = im2_aligned.mul(cv::Scalar(0, 0, 1), 1);
							addWeighted(im2_aligned, 0.5, detected_edges, 0.5, 0.0, detected_edges);
							cout << "Alignment failed\n";

						}*/


						//}
						// Storage for warped image.




						//chip_roi.copyTo(im2_aligned);

						//			cv::Mat chip(iHeight_, iWidth_, CV_8UC3, pBuffRGB_);
				}
			}
			//Latency test
			//double min, max;
			//minMaxLoc(image, &min, &max);
			//if ((max < 110) && (latency)) {
		//		cout << "Min " << min << " max " << max << "\n";
			//	double elapsedTime = ((static_cast<double>(cv::getTickCount()) - latency_time) / cv::getTickFrequency());
			//	cout << "Latency: " << elapsedTime << "\n";
			//	latency = false;
			//}
			//cout << "button_mode" << button_mode << " " << (switches | 0b000001) << "\n";
			if (button_mode != 0) {
				double elapsedTime = ((static_cast<double>(cv::getTickCount()) - prev_button_time) / cv::getTickFrequency());
				if (button_mode == -1) {
					//parse_command("STOP\n");
					parse_command("LH0\n");
					parse_command("LN10\n");
					if (0) {
						automating = false;
						auto_text = "";
						next_command = "";
					}
					//parse_command("STOP\n");
					parse_command("GRF0\n");
					parse_command("GCB5\n");
					button_mode = -2;
					prev_button_time = static_cast<double>(cv::getTickCount());
				}
				else if ((button_mode == -2) && (elapsedTime > 0.5)) {
					parse_command("LH8\n");
					button_mode = -3;
					prev_button_time = static_cast<double>(cv::getTickCount());
				}
				else if ((button_mode == -3) && (elapsedTime > 0.5)) {
					parse_command("LH0\n");
					button_mode = -4;
					prev_button_time = static_cast<double>(cv::getTickCount());
				}
				else if ((button_mode == -4) && (elapsedTime > 0.5)) {
					parse_command("LH8\n");
					button_mode = -5;
					prev_button_time = static_cast<double>(cv::getTickCount());
				}
				else if ((button_mode == -5) && (elapsedTime > 0.5)) {
					parse_command("LH0\n");
					button_mode = -6;
					//button_mode = 0;
					//prev_button_time = static_cast<double>(cv::getTickCount());
				} else if (button_mode == 1) {
					parse_command("LH0\n");
					button_mode = 2;
					prev_button_time = static_cast<double>(cv::getTickCount());
				}
				else if ((button_mode >= 2) && (button_mode < 14) && (elapsedTime > 0.5)) {
					
						string lighting_cmd = "LN";
						lighting_cmd = lighting_cmd + std::to_string(button_mode - 2) + "\n";
						parse_command(lighting_cmd);
						parse_command("LH8\n");
						button_mode++;
						prev_button_time = static_cast<double>(cv::getTickCount());
					
				} else if ((button_mode==14) && (elapsedTime > 0.5)) {
					button_mode = 15;
					parse_command("LH0\n");
					prev_button_time = static_cast<double>(cv::getTickCount());
				}
				else if ((button_mode == 15) && (elapsedTime > 5)) {
					button_mode = 0;
					if (0) {
						auto_file_num = "8";
						string auto_file = prefix+"automate" + auto_file_num + ".txt";
						cout << "START: " << auto_file << "\n";
						//ifstream fstm;
						//filestream.open(auto_file.c_str());
						ifstream is(auto_file);
						string str;
						//while (!automate.empty()) {
						//	automate.pop();
						//}
						automate.resize(0);
						//while (!automate.empty()) {
						//	automate_loop.pop();
						//}
						int start_auto = 0;
						while (getline(is, str))
						{
							if (auto_count >= start_auto) {
								//automate.push(str);
								automate.push_back(str);
								//automate_loop.push(str);
							}
							auto_count++;
							cout << auto_count << ": " << str << "\n";
						}
						//while (!automate.empty()) {
						//	cout << "auto: " << automate.front() << "\n";
						//	automate.pop();
						//}
						automating = true;
						automate_ind = 0;
						//static auto t = static_cast<double>(cv::getTickCount());
						prev_automate_time = static_cast<double>(cv::getTickCount());
						automate_delay = 0;
						auto_delay_type = "SLEEP0";
						auto_count = start_auto;
					}
					parse_command("STOP\n");
					parse_command("GRF122\n");
					////parse_command("START" + auto_file_num + "\n");
				}
				else if (button_mode == 100) {
					prev_button_time = static_cast<double>(cv::getTickCount());
					button_mode = 101;
				}
				else if ((button_mode == 101) && (elapsedTime > 5)) {
					button_mode = 0;
				}

			}
				if (run_hough_circles) {
					try {
						HoughCircles(detected_edges, circles, CV_HOUGH_GRADIENT, 1, 20, 50, 20, 150, 170);
						//HoughCircles(threshold_image, circles, CV_HOUGH_GRADIENT, 1, 20, 50, 20, 150, 170);
					}
					catch (exception &err) {
							cout << "Hough failed\n";
					}
					if (run_lighting) {
						if (0) {
						//if (lighting_type<2) {
							double elapsedTime = ((static_cast<double>(cv::getTickCount()) - prev_lighting_time) / cv::getTickFrequency());
							if (elapsedTime > 0.2) {
								prev_lighting_time = static_cast<double>(cv::getTickCount());
								double min, max;
								minMaxLoc(image, &min, &max);
								;
								cout << "Min " << min << " max " << max << "\n";
								if (lighting_type == 1) {
									//if (max == 255 && circles.size() != 0) {
									if (circles.size() != 0) {
										run_lighting = false;
										running = false;
										cout << "Got circle lighting\n";

										;								//lighting -= 8;
																		//string lighting_cmd = "LH";
																		//lighting_cmd = lighting_cmd + std::to_string(lighting) + "\n";
																		//cout << "LIGHTING: " << lighting_cmd << "\n";
																		//parse_command(lighting_cmd);
									}
									else {
										//lighting = lighting + 8;
										lighting = lighting - 8;
										//if (lighting > 255) {
										if (lighting < 0) {
											lighting = 63;
											run_lighting = false;
											running = false;
											cout << "Circle lighting failed\n";
										}
										string lighting_cmd = "LH";
										lighting_cmd = lighting_cmd + std::to_string(lighting) + "\n";
										cout << "LIGHTING: " << lighting_cmd << "\n";
										parse_command(lighting_cmd);
									}
								}
								else {
									if (max < 255) {
										run_lighting = false;
										running = false;
										cout << "Got lighting\n";
									}
									else {
										lighting = lighting - 8;
										if (lighting < 0) {

											lighting = 63;
											run_lighting = false;
											running = false;
											cout << "Lighting failed\n";
										}
										string lighting_cmd = "LH";
										lighting_cmd = lighting_cmd + std::to_string(lighting) + "\n";
										cout << "LIGHTING: " << lighting_cmd << "\n";
										parse_command(lighting_cmd);
									}
								}
							}
						}
						else {
							double min, max;
							cv::Mat mean, stddev;
							minMaxLoc(image, &min, &max);
							meanStdDev(image, mean,stddev);
							//cout << "MEAN\n";
							//cout << mean << "\n";
							//cout << mean.size() << "\n";
						    //cout << mean.at<double>(0) << "\n",
							//cout << "STDDEV\n";
							//cout << stddev(0,0) << "\n";
							lighting_min[lighting_ind] = min;
							lighting_max[lighting_ind] = max;
							lighting_mean[lighting_ind] = mean.at<double>(0);
							lighting_stddev[lighting_ind] = stddev.at<double>(0);

							lighting_circles[lighting_ind] = circles.size();
							
							double elapsedTime = ((static_cast<double>(cv::getTickCount()) - prev_lighting_time) / cv::getTickFrequency());
							if (elapsedTime > 10) {
								cout << "Lighting timed out\n";
								image_attempts++;
								timedout += 1;
								if (image_attempts >= 3) {
									string light_str = "LH7\n";
									parse_command(light_str);
									run_lighting = false;
									running = false;
									lighting_mode = 0;
									image_attempts = 0;
								}
								else {
									lighting_mode = 1;
									prev_lighting_time = static_cast<double>(cv::getTickCount());
									parse_command("LH64\n");
									lighting = 64;
									lighting_ind = 0;
								}
							} else
							if ((lighting_mode==1) && (elapsedTime > 0.2)) {
								cout << "LIGHTING START\n";
								string final_text = "I1\n";
								std::vector<char> chars(final_text.c_str(), final_text.c_str() + final_text.size() + 1u);
								bool serialerror = arduino->writeSerialPort(&chars[0], final_text.size());
								lighting_mode = 2;
								//parse_command("II1\n");
							} else if (lighting_mode == 2) {
								if (max * 1.5 < lighting_max[lighting_ind-1]) {
									lighting_mode = 3;
									lighting_ind = 0;
									lighting_min[lighting_ind] = min;
									lighting_max[lighting_ind] = max;
									lighting_mean[lighting_ind] = mean.at<double>(0);
									lighting_stddev[lighting_ind] = stddev.at<double>(0);
									lighting_circles[lighting_ind] = circles.size();
								}
							} else if (lighting_mode == 3) {
								if (max * 1.5 < lighting_max[lighting_ind - 1]) {
									lighting_mode = 0;
									//lighting_type = 0;
									bool got_light = false;
									int got_light_ind = 0;
									int size_max = 0;
									double size_max_av = 0;
									int size_max_count = 0;

									if (lighting_type == 1) {
										for (int i = lighting_ind - 1; i >= 0; i--) {
											cout << lighting_min[i] << " " << lighting_max[i] << " " << lighting_mean[i] << " " << lighting_stddev[i] << " " << lighting_circles[i] << "\n";
											if (lighting_circles[i] > size_max) {
												size_max = lighting_circles[i];
											}
										}
										for (int i = lighting_ind - 1; i >= 0; i--) {
											if (lighting_circles[i] == size_max) {
												size_max_av = size_max_av + i;
												size_max_count++;
											}
										}
										size_max_av /= size_max_count;
										if (size_max_av != 0) {
											got_light = true;
										}
										else {
											cout << "Circle lighting failed\n";
											string light_str = "LH63\n";
											parse_command(light_str);
											run_lighting = false;
											running = false;
											lighting_mode = 0;
										}
									}
									if (lighting_type == 0) {
										for (int i = lighting_ind - 1; i >= 0; i--) {
											cout << i << " " << lighting_min[i] << " " << lighting_max[i] << " " << lighting_mean[i] << " " << lighting_stddev[i] << " " << lighting_circles[i] << "\n";
											if (!got_light) {
												//if (lighting_circles[i] > 0) {
												if ((lighting_max[i] < 255) && (lighting_stddev[i]>10) &&
												(lighting_mean[i]>32) && (lighting_mean[i]<224)) {
													got_light = true;
													got_light_ind = i;
												}
											}
										}
									}
									cout << "circles " << size_max << " " << size_max_av << " " << size_max_count << "\n";
									if (got_light) {

										//cout << "Got light: " << lighting_ind << " " << got_light_ind << " " << lighting_min[got_light_ind] << " " << lighting_max[got_light_ind] << " " << lighting_circles[got_light_ind];
										//cout << "light = " << 256.0*(((float)(got_light_ind))/lighting_ind) << " ";
										//int final_light = (int)(256.0 * (((float)(got_light_ind)) / lighting_ind));
										int final_light = (int)(64.0 * (((float)(size_max_av)) / lighting_ind));;
										if (lighting_type == 0) {
											final_light = (int)(64.0 * (((float)(got_light_ind)) / lighting_ind));
											cout << "final ind " << got_light_ind << " " << final_light << "\n";
										}
										if (final_light < 0) final_light = 0;
										if (final_light > 63) final_light = 63;
										string light_str = "LH" + to_string(final_light) + "\n";
										parse_command(light_str);
										run_lighting = false;
										running = false;
										lighting_mode = 0;
										image_attempts = 0;
									}
								}
							}
							lighting_ind++;
							cout << std::to_string(1 / videoFramesPerSec_ * 1000) << " " << lighting_mode << " " << lighting_ind << " " << lighting_max[lighting_ind - 1] << " " << lighting_max[lighting_ind - 1] << " " << lighting_max[lighting_ind - 1] << " " << max << "\n";
							//cout << min << " " << max << " " << light << "\n";
						}
					}
				}
				//double min, max;
				//minMaxLoc(image, &min, &max);
				//cout << min << " " << max << " " << light << "\n";
				
				if (run_hough_lines) {
					//cvtColor(detected_edges, detected_edges, COLOR_GRAY2BGR);
				}
				if (run_hough_lines && (image_mode == IMAGE_OPENCV)) {
					// Draw the lines
					//cvtColor(image, image, COLOR_GRAY2BGR);

					//cout << "Theta:";
					/*
					for (size_t i = 0; i < lines.size(); i++)
					{
						float rho = lines[i][0], theta = lines[i][1];
						//if ((theta * 180 / 3.1415 < 95) && (theta * 180 / 3.1415 > 85)) {
						Point pt1, pt2;
						double a = cos(theta), b = sin(theta);
						double x0 = a * rho, y0 = b * rho;
						pt1.x = cvRound(x0 + 1000 * (-b));
						pt1.y = cvRound(y0 + 1000 * (a));
						pt2.x = cvRound(x0 - 1000 * (-b));
						pt2.y = cvRound(y0 - 1000 * (a));
						//cout << " " << theta * 180 / 3.1415;
						line(detecte\d_edges, pt1, pt2, Scalar(0, 0, 255), 3, LINE_AA);
						//}
					}
					*/

					for (size_t i = 0; i < lines.size(); i++)
					{
						line(image_debug, Point(lines[i][0], lines[i][1]),
							Point(lines[i][2], lines[i][3]), Scalar(255, 0, 0), 3, 8);
					}
					
					//cout << "\n";
				}
				if (run_hough_circles) {
					//cout << run_center << " " << circles.size() << " \n";
					if (run_center == 2) {
						if ((!motorBusy(6) && (!motorBusy(7)))) {
							run_center = 0;
							running = false;
							//run_center = 0;
							//running = false;
						}
					}
					//if (run_center == 3) {
					//	double elapsedTime = ((static_cast<double>(cv::getTickCount()) - prev_hough_time) / cv::getTickFrequency());
					//	if (elapsedTime > 0.1) {
					//		run_center = 0;
					//		running = false;
					//	}
					//}
					if (run_center == 1) {
						double elapsedTime = ((static_cast<double>(cv::getTickCount()) - prev_hough_time) / cv::getTickFrequency());
						if (elapsedTime > 2) {
							run_center = 0;
							running = false;
							cout << "CENTER FAILED!\n";
						}
					}

					if (circles.size() == 0) {
						hough_conf[hough_conf_ind] = 0;
					}
					else {
						hough_conf[hough_conf_ind] = 1;
					}
					hough_conf_ind++;
					if (hough_conf_ind >= HOUGH_CONF_IND_MAX) {
						hough_conf_ind = 0;
					}
					hough_conf_total = 0;
					for (int i = 0; i < HOUGH_CONF_IND_MAX; i++) {
						hough_conf_total += hough_conf[i];
					}
					/// Draw the circles detected
					//cout << "Size " << circles.size() << "\n";

					//cout << "Hough confidence: " << hough_conf_total << "\n";
					
					//if (circles.size() == 0 && run_center == 1) {
					//	cout << "FAILED!\n";
					//	run_center = 2;
					//}
					//if (circles.size() == 0
					for (size_t i = 0; i < circles.size(); i++)
					{
						
						 
						Point center_tmp(cvRound(circles[i][0]), cvRound(circles[i][1]));
						int radius = cvRound(circles[i][2]);
						//cout << "Radius " << radius << "\n";
						//cout << "Center " << center_tmp << "\n";
						// circle center
						//circle(detected_edges, center, 3, Scalar(0, 255, 0), -1, 8, 0);
						// circle outline
						if (i == 0) {
							//cout << "BUFFER " << hough_buffer_ind << "\n";
							//hough_buffer_ind++;
							
							if (run_center == 0) {
								circle(image_debug, center_tmp, radius, Scalar(0, 0, 255), 3, 8, 0);
								
							}
							//cout << "Radius " << radius << "\n";
							if (run_center==1) {
								centerx[center_count] = center_tmp.x;
								centery[center_count] = center_tmp.y;
								center_count++;
								//cout << "Count " << center_count << "\n";
								if (center_count >= centerx.size()) {
									sort(centerx.begin(), centerx.end());
									sort(centery.begin(), centery.end());
									Point center(centerx[centerx.size() / 2], centery[centery.size() / 2]);
									//cout << detected_edges.cols - center.x * 2 << " " << detected_edges.rows - center.y * 2 << "\n";
									double x_adjust = (detected_edges.cols - center.x * 2) / 600.0;
									double y_adjust = -(detected_edges.rows - center.y * 2) / 600.0;
									if (x_adjust > 0.5) {
										x_adjust = 0.5;
									}
									if (y_adjust > 0.5) {
										y_adjust = 0.5;
									}
									if (x_adjust < -0.5) {
										x_adjust = -0.5;
									}
									if (y_adjust < -0.5) {
										y_adjust = -0.5;
									}



									string center_text = "X" + to_string(-x_adjust) + " Y" + to_string(-y_adjust) + " F10\n";
									parse_command(center_text);
									center_fail = false;
									//60pixels to 0.1mm
									//See -, move + x
									//See -, move - y

									//cout << detected_edges.cols << " " << detected_edges.rows << "\n";
									//cout << "Radius " << radius << "\n";
									run_center = 2;
									//running = false;
								}
							}
						}
					}
					//Point centertest(0, 0);
					//circle(detected_edges, centertest, 160, Scalar(0, 0, 255), 3, 8, 0);
				}
				if (got_map) {
					//cvtColor(detected_edges, detected_edges, COLOR_GRAY2BGR);
					cvtColor(im2_aligned, im2_aligned, COLOR_GRAY2BGR);

					//cout << "Matrix: " << Mi[0] << " " << Mi[1] << " " << Mi[2] << " " << Mi[3] << "\n";
					//cout << "Matrix: " << warp_matrix.col(2).data << "\n";
					
					//chip_roi.copyTo(im2_aligned);
					im2_aligned = im2_aligned.mul(cv::Scalar(0, 1, 0), 1);
					//cout << im2_aligned.rows << " " << im2_aligned.cols << "\n";
					//cout << detected_edges.rows << " " << detected_edges.cols << "\n";
					addWeighted(im2_aligned, 0.5, image_debug, 0.5, 0.0, image_debug);
					//im2_aligned.copyTo(image_debug);
					//addWeighted(detected_edges, 0.5, detected_edges, 0.5, 0.0, detected_edges);
				}
			
			if (image_mode == IMAGE_OPENCV) {
				//detected_edges.copyTo(image);
				pyrUp(image_debug, image, Size(detected_edges.cols * 2, detected_edges.rows * 2));
			}
			if (image_mode == IMAGE_MICRO_PROJECTOR || image_mode == IMAGE_ALIGN) {
				if (projector.empty()) {
					cout << "Loading";
					Mat cad_img;
					//projector = imread("F:/themachine/projector/crosses.png", 0);
					//proj_ref = imread(prefix + "projector/proj_ref_multi.png", 0);
					proj_ref = imread(prefix + "projector/proj_ref_384_true.png", 0);
					//proj_ref = imread(prefix+"projector/proj_ref.png", 0);
					//proj_ref = imread(prefix + "projector/proj_ref_chip08.png", 0);

					//cv::resize(proj_ref, proj_ref, cv::Size(1000, 1000));
					//cv::imshow("Microscope rocker", proj_ref);
					//cv::waitKey(0);
					cad_img = proj_ref.clone();
					//cvtColor(proj_ref, cad_img, COLOR_BGR2GRAY);
					threshold(cad_img, cad_img, 128, 255, THRESH_BINARY);
					dilate(cad_img, cad_img, kernel);
					GaussianBlur(cad_img, cad_img, Size(21, 21), 30);

					//image_sub = real_img.clone();
					proj_ref = cad_img.clone();
					//cvtColor(cad_img, proj_ref, COLOR_GRAY2BGR);
					//proj_mask = imread(prefix+"projector/proj_mask.png", 0);
					projector = proj_ref;
					//cout << projector << "\n";
					update_proj = true;
					

				}
				else {
						

						if (update_proj) {
							//cout << "Update proj\n";
							cv::Mat proj_clone = projector.clone();
							cvtColor(proj_clone, proj_clone, COLOR_GRAY2BGR);
							int start_x = max(proj_targ_x, 10);
							int start_y = max(proj_targ_y, 10);

							int end_x = image.cols - 10;// min(proj_targ_x + proj_clone.cols, image.cols - 10);
							cout << "end_x" << proj_targ_x << " " << proj_clone.cols << " " << image.cols << "\n";
							//cout << "wtf??? " << image.cols << " " << image.rows << "\n";
							//cout << "wtf??? " << prev_image.cols << " " << prev_image.rows << "\n";
							int end_y = image.rows - 10;// (proj_targ_y + proj_clone.rows, image.rows - 10);

							//cout << "1\n";
							cout << "cropped funny\n";
							cout << "size " << proj_clone.size() << "\n";
							cv::resize(proj_clone, proj_clone, cv::Size(projector.cols * proj_targ_sx, projector.rows * proj_targ_sy), cv::INTER_LINEAR);
							cout << "size " << proj_clone.size() << "\n";
							cv::Point2f pc(proj_clone.cols / 2., proj_clone.rows / 2.);
							cv::Mat r = cv::getRotationMatrix2D(pc, proj_targ_r, 1.0);
							cv::warpAffine(proj_clone, proj_clone, r, proj_clone.size());
							//cout << "2\n";
							Rect image_roi(start_x, start_y, end_x - start_x, end_y - start_y);
							cout << "image roi " << start_x << " " << start_y << " " << end_x - start_x << " " << end_y - start_y << "\n";
							//cout << "2a\n";
							//cout << image_roi.size << "\n";
							Rect proj_roi(start_x - proj_targ_x, start_y - proj_targ_y, end_x - start_x, end_y - start_y);
							cout << end_x << " " << start_x << " " << end_y << " " << start_y << "\n";
							cout << "proj_targ_x: " << proj_targ_x << " proj_targ_y: " << proj_targ_y << "\n";
							
							//cout << image_roi.size << "\n";
							//cout << "2b\n";
							// Extract ROIs
							image_sub = image(image_roi);
							//cout << "2c\n";
							cout << start_x << " " << proj_targ_x << " " << start_y << " " << proj_targ_y << " " << end_x << " " << end_y << " " << proj_clone.size() << "\n";
							cvtColor(proj_clone, proj_adj, COLOR_BGR2GRAY);
							proj_sub = proj_clone(proj_roi);
							//cout << "2d\n";
							update_proj = false;
							//cout << "3\n";

							// Video sequence: ensure current frame and one-ahead frame
							// have been sent to the Pi. This runs after every update_proj
							// so the Pi always has the next frame buffered for instant swap.
							if (proj_video_sending) {
								static auto proj_video_prev_send_time = std::chrono::high_resolution_clock::now();
								// Set initial deadline when first frame is sent
								if (proj_video_index == 0 && proj_video_next_send == 0) {
									proj_video_deadline = std::chrono::high_resolution_clock::now()
										+ std::chrono::duration_cast<std::chrono::high_resolution_clock::duration>(
											std::chrono::duration<double>(proj_illum_time));
								}
								while (proj_video_next_send <= proj_video_index + 1 &&
									   proj_video_next_send < (int)proj_video_frames.size()) {
									auto send_now = std::chrono::high_resolution_clock::now();
									double dt = std::chrono::duration<double>(send_now - proj_video_prev_send_time).count();
									send_proj_frame_to_pi(proj_video_frames[proj_video_next_send], proj_illum_time, image.cols, image.rows);
									cout << "  Sent frame " << (proj_video_next_send + 1) << "/" << proj_video_frames.size()
										 << " dt=" << dt << "s\n";
									proj_video_prev_send_time = send_now;
									proj_video_next_send++;
								}
							}
						}

						// Video sequence: advance to next frame using accumulating deadline.
						// Deadline advances by exactly proj_illum_time each time, so
						// processing overhead doesn't accumulate.
						if (proj_video_sending && proj_video_index >= 0) {
							if (std::chrono::high_resolution_clock::now() >= proj_video_deadline) {
								proj_video_deadline += std::chrono::duration_cast<std::chrono::high_resolution_clock::duration>(
									std::chrono::duration<double>(proj_illum_time));
								proj_video_index++;
								if (proj_video_index < (int)proj_video_frames.size()) {
									projector = proj_video_frames[proj_video_index];
									update_proj = true;
									cout << "  Advancing to frame " << (proj_video_index + 1) << "/" << proj_video_frames.size() << "\n";
								} else {
									cout << "Video illumination complete.\n";
									projector = proj_video_frames.back();
									update_proj = true;
									proj_video_index = -1;
									proj_video_sending = false;
								}
							}
						}

						// Compute ROI in both images
						 // Preprocess real image
						if (align_mode!=0 || image_mode == IMAGE_ALIGN) {
							Mat real_img;
							cvtColor(image_sub, real_img, COLOR_BGR2GRAY);

							// --- START FIX ---
							// Create CLAHE object
							// clipLimit: Threshold for contrast limiting (try 2.0 to 4.0)
							// tileGridSize: Size of grid for histogram equalization (try 8x8)
							Ptr<CLAHE> clahe = createCLAHE(4.0, Size(8, 8));
							clahe->apply(real_img, real_img);
							// --- END FIX ---


							vector<Vec4f> real_lines = detect_lines_lsd(real_img);
							Mat line_image = Mat::zeros(real_img.size(), CV_8UC1);
							Mat line_image_bgr;
							cvtColor(line_image, line_image_bgr, COLOR_GRAY2BGR);
							Mat real_with_lines = draw_lines(line_image_bgr, real_lines, Scalar(255, 255, 255));
							threshold(real_with_lines, real_img, 128, 255, THRESH_BINARY);
							cvtColor(real_img, real_img, COLOR_BGR2GRAY);
							dilate(real_img, real_img, kernel);
							GaussianBlur(real_img, real_img, Size(21, 21), 30);
							cvtColor(real_img, image_sub, COLOR_GRAY2BGR);


							// Template Matching
							double low_score = DBL_MAX;
							double high_score = -DBL_MAX;
							Point final_min_loc, final_max_loc;
							//int final_ind = -1;
							int final_w = real_img.cols;
							int final_h = real_img.rows;


							//vector<Mat> cad_imgs;
							//vector<int> angles;
							//cad_imgs.push_back(proj_ref);

							//for (size_t x = 0; x < cad_imgs.size(); ++x) {
							Mat result;
							//matchTemplate(cad_imgs[x], real_img, result, TM_CCOEFF);
							matchTemplate(proj_adj, real_img, result, TM_CCOEFF_NORMED);
							double minVal, maxVal;
							Point minLoc, maxLoc;
							minMaxLoc(result, &minVal, &maxVal, &minLoc, &maxLoc);
							//if (maxVal > high_score) {
							high_score = maxVal;
							final_max_loc = maxLoc;
							cv::Rect cad_roi(maxLoc.x, maxLoc.y, real_img.cols, real_img.rows);
							cv::Mat cad_subimage = proj_adj(cad_roi);
							cv::Mat cad_mask;
							cv::threshold(cad_subimage, cad_mask, 50, 255, cv::THRESH_BINARY);  // threshold may need tuning
							cv::Mat real_masked;
							real_img.copyTo(real_masked, cad_mask);

							cv::Scalar mean, stddev;
							cv::meanStdDev(real_img, mean, stddev, cad_mask);
							double confidence = maxVal * stddev[0];  // optionally normalize
							cout << "Confidence " << confidence << "\n";
																								/*
							cv::Mat result64F;
							result.convertTo(result64F, CV_64F);
							cv::Mat lap;
							cv::Laplacian(result64F, lap, CV_64F);
							double peakiness = std::abs(lap.at<double>(maxLoc));  // higher = sharper
							cout << "Peakiness " << peakiness << "\n";
							*/
							//final_ind = x;
						//}
					//}
						
								cout << "Match: " << final_max_loc << "\n";
								cout << "proj_targ_x " << proj_targ_x << " proj_targ_y " << proj_targ_y << " " << " proj_targ_sx " << proj_targ_sx << " proj_targ_sy " << proj_targ_sy << "\n";
								
								if (confidence > 30) {
									if (align_mode == 2) {
										double x_adjust = (final_max_loc.x + proj_targ_x) / 300.0;
										double y_adjust = (final_max_loc.y + proj_targ_y) / 300.0;
										if (x_adjust > 2.0) {
											x_adjust = 2.0;
										}
										if (y_adjust > 2.0) {
											y_adjust = 2.0;
										}
										if (x_adjust < -2.0) {
											x_adjust = -2.0;
										}
										if (y_adjust < -2.0) {
											y_adjust = -2.0;
										}

										string center_text = "X" + to_string(-x_adjust) + " Y" + to_string(y_adjust) + " F10\n";
										parse_command(center_text);
									}
									if (align_mode == 1) {
										proj_targ_x = -final_max_loc.x;
										proj_targ_y = -final_max_loc.y;


									}
								}


								align_mode = 0;
								update_proj = true;
						}
						//Mat best_img = proj_ref;// cad_imgs[final_ind];
							//Point top_left = final_max_loc;
							//Point bottom_right(top_left.x + final_w, top_left.y + final_h);

							//rectangle(best_img, top_left, bottom_right, Scalar(255), 2);

							//Mat matched_cad_region = best_img(Rect(top_left, bottom_right));
							//Mat blended;
							//addWeighted(matched_cad_region, 0.5, real_img(Rect(top_left, bottom_right)), 0.5, 0, blended);



						// Ensure both sub-images are of the same type
						CV_Assert(image_sub.type() == proj_sub.type());

						// Blend the images (simple alpha blending)
						float alpha = 0.2;// 0.2;
						addWeighted(image_sub, 1.0 - alpha, proj_sub, alpha, 0.0, image_sub);
						cv::Point topLeft(200, 50);       // top-left corner
						int sideLength_x = 880;
						int sideLength_y = 800;// length of the square side
						cv::Point bottomRight = topLeft + cv::Point(sideLength_x, sideLength_y);

						// Draw the square (rectangle with equal sides)
						cv::Scalar color(0, 0, 255);       // Red color (BGR format)
						int thickness = 2;                 // Thickness of the line
						cv::rectangle(image_sub, topLeft, bottomRight, color, thickness);
						/*
						int min_x = int(proj_targ_x);
						int min_y = int(proj_targ_y);
						cv::Mat proj_clone = projector.clone();
						cv::resize(proj_clone, proj_clone, cv::Size(projector.cols * proj_targ_s, projector.rows * proj_targ_s), cv::INTER_LINEAR);
						cv::Point2f pc(proj_clone.cols / 2., proj_clone.rows / 2.);
						cv::Mat r = cv::getRotationMatrix2D(pc, proj_targ_r, 1.0);
						cv::warpAffine(proj_clone, proj_clone, r, proj_clone.size());

						cv::Rect roi = cv::Rect(min_x, min_y, image.cols, image.rows);
						proj_clone = proj_clone(roi);
						cvtColor(proj_clone, proj_clone, COLOR_GRAY2BGR);

						addWeighted(image, 0.5, proj_clone, 0.5, 0.0, image);
						std::cout << proj_targ_x << " " << proj_targ_y << " " <<
							proj_targ_s << " " << proj_targ_r << "\n";
							*/
							// -3025 - 3125 1.8 - 90
						//-3050 -3150 0.45 -90

						//std::cout << proj_targ_x << " " << proj_targ_y << " " <<
						//	proj_targ_s << " " << proj_targ_r << "\n";
					
				}
				//detected_edges.copyTo(image);
				//pyrUp(image_debug, image, Size(detected_edges.cols * 2, detected_edges.rows * 2));
			}
			else if (image_mode == IMAGE_MICRO_OPENCV) {
				//pyrUp(detected_edges, detected_edges_large, Size(detected_edges.cols * 2, detected_edges.rows * 2));
			}
			if (scale!=1) {
				//cv::Rect roi;
				// Calculate new dimensions
				float scaleFactor = 1.0/scale;
				int newWidth = static_cast<int>(image.cols* scaleFactor);
				int newHeight = static_cast<int>(image.rows* scaleFactor);

				// Calculate cropping offsets to keep the image centered
				int xOffset = (image.cols - newWidth) / 2;
				int yOffset = (image.rows - newHeight) / 2;

				// Crop the image if necessary
				cv::Rect roi(xOffset, yOffset, newWidth, newHeight);
				image = image(roi);

				// Resize the cropped or original image to the new dimensions
				//cv::Mat resizedImage;
				cv::resize(image, image, cv::Size(newWidth/scaleFactor, newHeight/scaleFactor));
				//int mid_x = int(image.size().width / 2);
				//int mid_y = int(image.size().height / 2);
				//int size_x = image.size().width/scale/2;
				//int size_y = image.size().height/scale/2;
				//cv::Mat image = image(Range(mid_x- size_x, mid_x+ size_x), Range(mid_y-size_y, mid_y+size_y));
				//mid_x, mid_y = int(width / 2), int(height / 2)
				//cw2, ch2 = int(crop_width / 2), int(crop_height / 2)
				//crop_img = img[mid_y - ch2:mid_y + ch2, mid_x - cw2 : mid_x + cw2]
				//resize(image, image, cv::Size(), scale, scale);
			}
			/// Using Canny's output as a mask, we display our result
			//dst = Scalar::all(0);

			//src.copyTo(dst, detected_edges);
			//cvtColor(image, image, COLOR_GRAY2BGR);
			int text_y = 70;
			string image_text = fps_str;
			cv::putText(image, image_text, cvPoint(30, text_y),
				cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
			//cout << fps << "\n";
			image_text = "X: " + to_string(camera_offset_x);
			text_y += 20;
			long focusa_pos = 0;
			long focusb_pos = 0;
			long obja_pos = 0;
			long microc_pos = 0;
			long tilta_pos = 0;
			long tiltb_pos = 0;
			long microa_pos = 0;
			long microb_pos = 0;

			if (motorBusy(6)) {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 0, 255), 1, CV_AA);
			}
			else {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
			}

			image_text = "Y: " + to_string(camera_offset_y);
			text_y += 20;
			if (motorBusy(3)) {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 0, 255), 1, CV_AA);
			}
			else {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
			}
			
			image_text = "Z: " + to_string(camera_offset_z);
			text_y += 20;
			if (motorBusy(0)) {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 0, 255), 1, CV_AA);
			}
			else {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
			}

			image_text = "O: " + to_string(objective_offset) + " [" + to_string(objective_mag) + "X]";
			text_y += 20;
			if (motorBusy(0)) {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 0, 255), 1, CV_AA);
			}
			else {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
			}

			/*
			image_text = "LED: " + to_string(led_num) + ", " + to_string(led_mag);
			text_y += 20;
			cv::putText(image, image_text, cvPoint(30, text_y),
				cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(255, 255, 255), 1, CV_AA);
				*/
			
			image_text = "FRONT BELT: " + to_string(front_belt);
			text_y += 20;
			if (motorBusy(5)) {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 0, 255), 1, CV_AA);
			}
			else {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
			}

			image_text = "FRONT ANGLE: " + to_string(front_rocker_angle);
			text_y += 20;
			if (motorBusy(5)) {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 0, 255), 1, CV_AA);
			}
			else {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
			}
			//image_text = "Noise: " + to_string(front_noise_max);
			//text_y += 20;
			//if (motor_busy[4] == 0) {
			//	cv::putText(image, image_text, cvPoint(30, text_y),
			//		cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
			//}
			//else {
			//	cv::putText(image, image_text, cvPoint(30, text_y),
			//		cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 0, 255), 1, CV_AA);
			//}
			//on, up, accel, step;

			image_text = "BACK BELT: " + to_string(back_belt);
			//on, up, accel, step;
			text_y += 20;
			if (motorBusy(4)) {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 0, 255), 1, CV_AA);
			}
			else {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
			}
			image_text = "BACK ANGLE: " + to_string(back_rocker_angle);
			//on, up, accel, step;
			text_y += 20;
			if (motorBusy(4)) {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 0, 255), 1, CV_AA);
			}
			else {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
			}
			//image_text = "NOISE: " + to_string(back_noise_max);
			//on, up, accel, step;
			//text_y += 20;
			//if (motor_busy[5] == 0) {
			//	cv::putText(image, image_text, cvPoint(30, text_y),
			//		cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
			//}
			//else {
			//	cv::putText(image, image_text, cvPoint(30, text_y),
			//		cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 0, 255), 1, CV_AA);
			//}
			image_text = "SWITCHES: " + std::bitset<5>(switches>>1).to_string();//to_string(switches);
			//on, up, accel, step;
			text_y += 20;
			if ((switches & 0b000001) == 0) {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
			}
			else {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 0, 255), 1, CV_AA);
			}

			image_text = "CO2: " + to_string(co2);//to_string(switches);
			//on, up, accel, step;
			text_y += 20;
			if (1) {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
			}
			else {
				cv::putText(image, image_text, cvPoint(30, text_y),
					cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 0, 255), 1, CV_AA);
			}
			string lightnum_str = "";
			if (lightnum >= 0 && lightnum < 6) {
				lightnum_str = "Back " + to_string(lightnum + 1);
			}
			else if (lightnum >= 6 && lightnum < 12) {
					lightnum_str = "Front " + to_string(lightnum - 5);
			} else {
				lightnum_str = "None ";
			}
			//image_text = "LED " + to_string(lightnum) + ": " + to_string(light);
			image_text = "LED " + lightnum_str + ": " + to_string(light);
			text_y += 20;
			cv::putText(image, image_text, cvPoint(30, text_y),
				cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);

			string chip_str = "";
			if (current_chip >= 0 && current_chip < 6) {
				chip_str = "Back " + to_string(current_chip + 1);
			}
			else if (current_chip >= 6 && current_chip < 12) {
				chip_str = "Front " + to_string(current_chip - 5);
			}
			else {
				chip_str = "None ";
			}
			//image_text = "Chip: " + to_string(current_chip);
			image_text = "Chip: " + chip_str;
			text_y += 20;
			cv::putText(image, image_text, cvPoint(30, text_y),
				cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);

			image_text = "Well: " + to_string(well_number);
			text_y += 20;
			cv::putText(image, image_text, cvPoint(30, text_y),
				cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);

			image_text = "Timedout: " + to_string(timedout);
			text_y += 20;
			cv::putText(image, image_text, cvPoint(30, text_y),
				cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
			
			image_text = "Attempt: " + to_string(image_attempts);
			text_y += 20;
			cv::putText(image, image_text, cvPoint(30, text_y),
				cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
				
			image_text = "Last command: " + last_command;
			text_y += 20;
			cv::putText(image, image_text, cvPoint(30, text_y),
				cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
			image_text = "Next command: " + next_command;
			text_y += 20;
			cv::putText(image, image_text, cvPoint(30, text_y),
				cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
			image_text = "Program: ";
			if (automating) {
				image_text = image_text + "Running ";
			}
			if (program_paused!=0) {
				image_text = image_text + "Paused";
			}
			text_y += 20;
			cv::putText(image, image_text, cvPoint(30, text_y),
				cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);

			//cout << "Camera: " << camera_offset_x << " " << camera_offset_y << "\n";
			cv::putText(image, input_text, cvPoint(30, 30),
				cv::FONT_HERSHEY_COMPLEX_SMALL, 0.6, cvScalar(0, 255, 0), 1, CV_AA);
			//cv::circle(image, laser, 400, Scalar(128, 128, 255), 1, 8, 0);



			// Poll commands every frame for responsive mouse/projector drag
			{
				zmq::message_t cmd_msg;
				while (cmd_socket.recv(cmd_msg, zmq::recv_flags::dontwait)) {
					parse_command(cmd_msg.to_string());
				}
			}

			cv::imshow("Microscope", image);

			// JPEG-compress and send via ZMQ (matching zmq_sender.py)
			if (image_send) {
				std::vector<uchar> jpg_buf;
				std::vector<int> encode_params = { cv::IMWRITE_JPEG_QUALITY, 60 };
				cv::imencode(".jpg", image, jpg_buf, encode_params);
				zmq::message_t img_msg(jpg_buf.data(), jpg_buf.size());
				image_socket.send(img_msg, zmq::send_flags::dontwait);
			}

			char chr = cv::waitKey(1);

			if (chr != -1) {
				//std::cout << "chr" << chr << "\n";
				if (chr == 8) {
					//cout << input_text.size() << "\n";
					if (input_text.size() > 0) {
						input_text = input_text.substr(0, input_text.size() - 1);
					}
				}
				else if (chr == 27) {
					cout << "quit" << '\n';
					//fclose(stderr);
					//log_file.close();
					acc_file.close();
					store();
					cv::destroyAllWindows();
					_Exit(0);
				}
				else if (chr == 9) {
					if (program_paused == 0) program_paused = 1;
					else program_paused = 0;
				}
				else if (chr == 13) {
					input_text = input_text + '\n';
					parse_command(input_text);
					
					
					
					/*if (input_text == "U") {
						exposure += 100;
						if (video_in->set_exposure(exposure) == false)
						{
							exposure-=100;
						}
						std::cout << "exposure " << exposure << std::endl;
					}
					if (input_text == "D") {
						exposure -= 100;
						if (`->set_exposure(exposure) == false)
						{
							exposure+=100;
						}
						std::cout << "exposure " << exposure << std::endl;
					}*/
					input_text = "";

				}
				else if (chr == '-' || (chr >= 'a' && chr <= 'z') || (chr >= 'A' && chr <= 'Z') || chr == ' ' || chr == '.'
					|| (chr >= '0' && chr <= '9')) {
					input_text = input_text + (char)toupper(chr);
				}
			}

		} 
		if (taking_picture) {
			time_t now = time(0);
			struct tm tstruct;
			char buf[80];
			tstruct = *localtime(&now);
			strftime(buf, sizeof(buf), "%Y-%m-%d-%H-%M-%S", &tstruct);
			std::string time_str(buf);
			string frame_file = prefix+pic_dir+"/Image_";//"../../Image_";
			string meta_file = prefix+pic_dir+"/Image_";
			auto chrono_end_time = std::chrono::high_resolution_clock::now();
			auto chrono_time = chrono_end_time - chrono_start_time;
			string chrono_str = std::to_string(chrono_time / std::chrono::microseconds(1));
			frame_file = frame_file + time_str + "-" + chrono_str + ".png";
			meta_file = meta_file + time_str + "-" + chrono_str + ".txt";
			cout << frame_file;
			util_image::raw_to_rgb(pBuffRaw_[0], 0, pBuffRGB_, 0, iWidth_* iHeight_, bitsPerPix_);
			cv::Mat image(iHeight_, iWidth_, CV_8UC3, pBuffRGB_);
			cv::flip(image, image, 1);
			//cv::imwrite(frame_file, image);

			cvtColor(image, image, COLOR_BGR2GRAY);
			cv::imwrite(frame_file, image, { cv::ImwriteFlags::IMWRITE_PNG_COMPRESSION, 9 });
			write_meta_file(meta_file);
			taking_picture = false;

			//string optipng = "wsl optipng /mnt/d/themachine/Image_";
			//optipng = optipng + time_str + ".png";
			//system(optipng.c_str());
			std::cout << "Saved image" << "\n";


		}

		if (video_frame == num_frames) {
			video_save = 1;
			video_frame = 0;
			recording_video = false;

			
			time_t now = time(0);
			struct tm tstruct;
			char buf[80];
			tstruct = *localtime(&now);
			strftime(buf, sizeof(buf), "%Y-%m-%d-%H-%M-%S", &tstruct);
			std::string time_str(buf);
			std::cout << "Done recording video\n";
			video_frame = 0;
			recording_video = false;
			std::cout << "Saving video\n";
			string video_folder = prefix+"Video_";
			video_folder = video_folder + time_str;
			CreateDirectoryA(video_folder.c_str(), NULL);
			//string video_file = "D:/video_test/Video_";//"../../Image_";
			auto chrono_end_time = std::chrono::high_resolution_clock::now();
			auto chrono_time = chrono_end_time - chrono_start_time;
			string chrono_str = std::to_string(chrono_time / std::chrono::microseconds(1));
			string meta_file = video_folder + "/Video_" + time_str + "-" + chrono_str + ".txt";
			//video_file = video_file + time_str + ".avi";
			//meta_file = meta_file + time_str + ".txt";
			
			//ofstream myFile("F:/themachine/data.bin", ios::out | ios::binary);
			//cout << "video bytes " << video_bytes << "\n";
			//myFile.write((char*)&pBuffRaw_, video_bytes);// video_bytes);
			//myFile.close();
			
			//char buffer[100];
			//ofstream myFile("F:/themachine/data.bin", ios::out | ios::binary);
			//myFile.write(buffer, 100);
			//myFile.close();
			double start_time = static_cast<double>(cv::getTickCount());
			/*
			VideoWriter video(video_file, CV_FOURCC('M', 'J', 'P', 'G'), 60, Size(iWidth_, iHeight_));
			//cout << "backend " << cv::VideoWriter::getBackendName() << "\n";
			int codec = video.get(VIDEOWRITER_PROP_NSTRIPES);
			cout << "codec " << codec << "\n";

			*/
			/*
			for (int i = 0; i < NUM_FRAMES; i++) {
				util_image::raw_to_rgb(pBuffRaw_[i], 0, pBuffRGB_, 0, iWidth_*iHeight_, bitsPerPix_);
				cv::Mat image(iHeight_, iWidth_, CV_8UC3, pBuffRGB_);
				cv::flip(image, image, 1);
				cvtColor(image, image, COLOR_BGR2GRAY);
				string frame_file = video_folder + "/" + format("Imageopencv_%03d.png", i);
				cv::imwrite(frame_file, image);
				//video.write(image);
				std::cout << "Saved frame " << i << "\n";
			}*/
			
			//video.release();
			
			
			//string ffmpegCommand = "C:\\Users\\themachine_desktop\\Downloads\\ffmpeg-2021-12-06-git-ef00d40e32-full_build\\bin\\ffmpeg.exe -y -f rawvideo -vcodec rawvideo -framerate 60 -pix_fmt bgr24 -s 1280x720 -i - -c:v h264_nvenc -crf 14 -maxrate:v 10M -r 50 D:\\myVideoFile.mkv";
			//string ffmpegCommand = "C:\\Users\\themachine_desktop\\Downloads\\ffmpeg-2021-12-06-git-ef00d40e32-full_build\\bin\\ffmpeg.exe -y -f rawvideo -vcodec rawvideo -framerate 60 -pix_fmt bgr24 -s 1280x720 -i - -c:v libx264 -crf 0 D:\\video_test\\test.mp4";
			//string ffmpegCommand = "C:\\Users\\themachine_desktop\\Downloads\\ffmpeg-2021-12-06-git-ef00d40e32-full_build\\bin\\ffmpeg.exe -y -f rawvideo -vcodec rawvideo -framerate 60 -pix_fmt bgr24 -s 1280x720 -i - -c:v libx264rgb  -crf 0 D:\\output2.mp4";
			//string ffmpegCommand = "C:\\Users\\themachine_desktop\\Downloads\\ffmpeg-2021-12-06-git-ef00d40e32-full_build\\bin\\ffmpeg.exe -y -f rawvideo -vcodec rawvideo -framerate 60 -pix_fmt bgr24 -s 1280x720 -i - -c:v copy  -crf 0 D:\\output3.mp4";
			//string ffmpegCommand = "C:\\Users\\themachine_desktop\\Downloads\\ffmpeg-2021-12-06-git-ef00d40e32-full_build\\bin\\ffmpeg.exe -f rawvideo -pix_fmt gray -s 1280x720 -i - \"D:\\video_test\\test-%03d.png\"";

			//To convert pngs to Windows playable video:
			//ffmpeg -framerate 60 -i themachine/Video_2021-12-10-13-02-26/Image-%03d.png -c:v libx264 -strict -2 -preset slow -pix_fmt yuv420p -crf 1 -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" -f mp4 ./test.mp4
			//crf 18 for much smaller file size

			//"C:\dev\ffmpeg-2026-01-19-git-43dbc011fa-essentials_build\ffmpeg-2026-01-19-git-43dbc011fa-essentials_build\bin\ffmpeg.exe"
			string ffmpegCommand = "C:\\Users\\davidsachs\\Documents\\ffmpeg-2025-04-23-git-25b0a8e295-essentials_build\\bin\\ffmpeg.exe -f rawvideo -pix_fmt gray -s 1280x960 -i - ";
			//string ffmpegCommand = "F:\\Downloads\\ffmpeg-2025-04-23-git-25b0a8e295-essentials_build\\bin\\ffmpeg.exe -f rawvideo -pix_fmt gray -s 1280x960 -i - ";
			//string ffmpegCommand = "C:\\Users\\themachine_desktop\\Downloads\\ffmpeg-2021-12-06-git-ef00d40e32-full_build\\bin\\ffmpeg.exe -f rawvideo -pix_fmt gray -s 1280x720 -i - ";
			//string ffmpegCommand = "C:\\Users\\themachine_desktop\\Downloads\\ffmpeg-2021-12-06-git-ef00d40e32-full_build\\bin\\ffmpeg.exe -f rawvideo -pix_fmt gray -s 1280x960 -i - ";
			ffmpegCommand = ffmpegCommand + video_folder + "/" + "Image-%03d.png";
			//for (int i = 0; i < NUM_FRAMES; i++) {
			//	ffmpegCommand = ffmpegCommand + video_folder + "/" + "Image-%03d.png";
			//}
			cout << "FFMPEG Command: " << ffmpegCommand << "\n";
			FILE* pipeout = _popen(ffmpegCommand.data(), "wb");
			// -pix_fmt yuv420p
			//int id = metaDataWriter.insertNow(path);

			//loop will be stopped from another thread
			//while (this->isRunning) {
				//this->frames is a stack with cv::Mat elements in the right order
				//it is filled by another thread
				//while (!this->frames.empty()) {
			for (int i = 0; i < num_frames; i++) {
				util_image::raw_to_rgb(pBuffRaw_[i], 0, pBuffRGB_, 0, iWidth_* iHeight_, bitsPerPix_);
				cv::Mat image(iHeight_, iWidth_, CV_8UC3, pBuffRGB_);
				cv::flip(image, image, 1);
				cvtColor(image, image, COLOR_BGR2GRAY);
				//cv::Mat mat = frames.front();
				//frames.pop();
				
				fwrite(image.data, 1228800, 1, pipeout);

				//fwrite(image.data, 921600, 1, pipeout);
				//cout << "Chrono: " << chrono_frame_time;
				//std::cout << "Saved frame " << i << " " << video_bytes << "\n";
				//Sleep(100);
				//}
			//}
			}

			fflush(pipeout);
			_pclose(pipeout);

			write_meta_file(meta_file, true);
			
			double elapsedTime = ((static_cast<double>(cv::getTickCount()) - start_time) / cv::getTickFrequency());
			
			std::cout << "Done saving video\n";
			std::cout << "Time: " << elapsedTime << "\n";

			run_hough_circles = true;
			run_hough_lines = true;
		}
	}



};
