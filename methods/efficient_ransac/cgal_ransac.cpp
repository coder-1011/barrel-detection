// Efficient RANSAC (Schnabel et al. 2007) cylinder detection via CGAL's
// reference implementation (CGAL::Shape_detection::Efficient_RANSAC).
//
// This is a *self-contained* primitive detector: unlike methods #2/#3 it needs
// no clustering proposer -- it finds cylinders directly among the points,
// registering Plane + Cylinder shape factories and reporting the cylinders.
//
// Input : ASCII "x y z nx ny nz" per line, in METERS (normals required).
// Output: one line per detected cylinder, METERS:
//           CYL <radius> <cx cy cz> <ax ay az> <extent> <n_inliers>
//         where (cx,cy,cz) is the midpoint of the inlier span along the axis.
//
// Build : methods/efficient_ransac/build.sh  (header-only CGAL; needs gmp/mpfr)
#include <CGAL/Exact_predicates_inexact_constructions_kernel.h>
#include <CGAL/property_map.h>
#include <CGAL/Random.h>
#include <CGAL/Shape_detection/Efficient_RANSAC.h>

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <limits>
#include <sstream>
#include <vector>

typedef CGAL::Exact_predicates_inexact_constructions_kernel Kernel;
typedef Kernel::FT FT;
typedef std::pair<Kernel::Point_3, Kernel::Vector_3> Pwn;
typedef std::vector<Pwn> Pwn_vector;
typedef CGAL::First_of_pair_property_map<Pwn> Point_map;
typedef CGAL::Second_of_pair_property_map<Pwn> Normal_map;
typedef CGAL::Shape_detection::Efficient_RANSAC_traits<Kernel, Pwn_vector,
                                                       Point_map, Normal_map> Traits;
typedef CGAL::Shape_detection::Efficient_RANSAC<Traits> Efficient_ransac;
typedef CGAL::Shape_detection::Cylinder<Traits> Cylinder;
typedef CGAL::Shape_detection::Plane<Traits> Plane;

int main(int argc, char** argv) {
  if (argc < 2) {
    std::cerr << "usage: " << argv[0]
              << " <xyzn.txt> [epsilon] [cluster_epsilon] [min_points]"
                 " [normal_threshold] [probability]\n";
    return 2;
  }
  const std::string path = argv[1];
  const double epsilon          = (argc > 2) ? std::atof(argv[2]) : 0.003;
  const double cluster_epsilon  = (argc > 3) ? std::atof(argv[3]) : 0.01;
  const std::size_t min_points  = (argc > 4) ? std::strtoul(argv[4], nullptr, 10) : 200;
  const double normal_threshold = (argc > 5) ? std::atof(argv[5]) : 0.9;
  const double probability      = (argc > 6) ? std::atof(argv[6]) : 0.05;
  const unsigned seed           = (argc > 7) ? std::strtoul(argv[7], nullptr, 10) : 42;

  // Seed CGAL's RNG so Efficient_RANSAC is reproducible run-to-run.
  CGAL::get_default_random() = CGAL::Random(seed);
  std::srand(seed);

  Pwn_vector points;
  {
    std::ifstream in(path);
    if (!in) { std::cerr << "cannot open " << path << "\n"; return 1; }
    std::string line;
    while (std::getline(in, line)) {
      if (line.empty() || line[0] == '#') continue;
      std::istringstream ss(line);
      double x, y, z, nx, ny, nz;
      if (ss >> x >> y >> z >> nx >> ny >> nz) {
        points.emplace_back(Kernel::Point_3(x, y, z),
                            Kernel::Vector_3(nx, ny, nz));
      }
    }
  }
  std::cerr << "loaded " << points.size() << " points with normals\n";
  if (points.size() < min_points) {
    std::cerr << "too few points (" << points.size() << " < " << min_points << ")\n";
    return 0;
  }

  Efficient_ransac ransac;
  ransac.set_input(points);
  ransac.add_shape_factory<Plane>();
  ransac.add_shape_factory<Cylinder>();

  Efficient_ransac::Parameters params;
  params.probability = probability;
  params.min_points = min_points;
  params.epsilon = epsilon;
  params.cluster_epsilon = cluster_epsilon;
  params.normal_threshold = normal_threshold;

  if (!ransac.detect(params)) {
    std::cerr << "detection failed\n";
    return 1;
  }
  std::cerr << ransac.shapes().end() - ransac.shapes().begin()
            << " shape(s) detected\n";

  for (const auto& sh : ransac.shapes()) {
    Cylinder* cyl = dynamic_cast<Cylinder*>(sh.get());
    if (!cyl) continue;
    Kernel::Line_3 ax = cyl->axis();
    Kernel::Point_3 p0 = ax.point();
    Kernel::Vector_3 d = ax.to_vector();
    double dn = std::sqrt(CGAL::to_double(d.squared_length()));
    if (dn < 1e-12) continue;
    double dx = CGAL::to_double(d.x()) / dn;
    double dy = CGAL::to_double(d.y()) / dn;
    double dz = CGAL::to_double(d.z()) / dn;
    double px = CGAL::to_double(p0.x()), py = CGAL::to_double(p0.y()),
           pz = CGAL::to_double(p0.z());

    // inlier span along the axis -> extent + a centered point on the axis
    double tmin = std::numeric_limits<double>::infinity();
    double tmax = -std::numeric_limits<double>::infinity();
    const auto& idx = sh->indices_of_assigned_points();
    for (std::size_t i : idx) {
      const Kernel::Point_3& q = points[i].first;
      double t = (CGAL::to_double(q.x()) - px) * dx
               + (CGAL::to_double(q.y()) - py) * dy
               + (CGAL::to_double(q.z()) - pz) * dz;
      if (t < tmin) tmin = t;
      if (t > tmax) tmax = t;
    }
    double tmid = 0.5 * (tmin + tmax);
    double cx = px + dx * tmid, cy = py + dy * tmid, cz = pz + dz * tmid;
    double extent = tmax - tmin;
    double r = CGAL::to_double(cyl->radius());

    std::cout << "CYL " << r << " " << cx << " " << cy << " " << cz << " "
              << dx << " " << dy << " " << dz << " " << extent << " "
              << idx.size() << "\n";
  }
  return 0;
}
