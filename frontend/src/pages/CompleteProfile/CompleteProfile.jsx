import React, { useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import API from "../../services/api";

import {
  FaUser,
  FaBirthdayCake,
  FaVenusMars,
  FaBriefcase,
  FaHospital,
  FaStethoscope,
  FaArrowRight,
} from "react-icons/fa";

import "./CompleteProfile.css";

export default function CompleteProfile() {

  const navigate = useNavigate();

  const [formData, setFormData] = useState({

    full_name: "",

    age: "",

    gender: "",

    occupation: "",

    hospital: "",

    specialization: "",

  });

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");

  const handleChange = (e) => {

    setFormData({

      ...formData,

      [e.target.name]: e.target.value,

    });

  };

  const handleSubmit = async (e) => {

    e.preventDefault();

    if (
  !formData.full_name.trim() ||
  !formData.age ||
  !formData.gender
) {

  setError("Please fill all required fields.");

  return;

}

    setLoading(true);

    setError("");

    try {

      const email = localStorage.getItem("email");

      await API.post(

        "/auth/profile",

        {

          email,

          full_name: formData.full_name,

          age: Number(formData.age),

          gender: formData.gender,

          occupation: formData.occupation,

        }

      );

      navigate("/dashboard");

    }

    catch (err) {

  console.error(err);

  setError(

    err.response?.data?.detail ||

    "Unable to save profile."

  );

}
    finally {

      setLoading(false);

    }

  };

  return (

    <div className="profile-page">

      <motion.div
        className="profile-card"
        initial={{
          opacity: 0,
          y: 30,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
        transition={{
          duration: 0.5,
        }}
      >

        <h1>

          Welcome to Oncology AI

        </h1>

        <p>

          Before we begin,
          let's personalize your
          clinical workspace.

        </p>

        <form onSubmit={handleSubmit}>

          <div className="input-group">

            <label>

              <FaUser />

              Full Name *

            </label>

            <input
              type="text"
              name="full_name"
              placeholder="Enter your full name"
              value={formData.full_name}
              onChange={handleChange}
              required
            />

          </div>

          <div className="row">

            <div className="input-group">

              <label>

                <FaBirthdayCake />

                Age *

              </label>

              <input
                type="number"
                name="age"
                placeholder="Age"
                min="1"
                max="120"
                value={formData.age}
                onChange={handleChange}
                required
              />

            </div>

            <div className="input-group">

              <label>

                <FaVenusMars />

                Gender *

              </label>

              <select
                name="gender"
                value={formData.gender}
                onChange={handleChange}
                required
              >

                <option value="">
                  Select Gender
                </option>

                <option value="Male">
                  Male
                </option>

                <option value="Female">
                  Female
                </option>

                <option value="Other">
                  Other
                </option>

                <option value="Prefer not to say">
                  Prefer not to say
                </option>

              </select>

            </div>

          </div>
                    <div className="input-group">

            <label>

              <FaBriefcase />

              Occupation (Optional)

            </label>

            <select
              name="occupation"
              value={formData.occupation}
              onChange={handleChange}
            >

              <option value="">
                Select Occupation
              </option>

              <option value="Doctor">
                Doctor
              </option>

              <option value="Medical Student">
                Medical Student
              </option>

              <option value="Researcher">
                Researcher
              </option>

              <option value="Radiologist">
                Radiologist
              </option>

              <option value="Pathologist">
                Pathologist
              </option>

              <option value="Healthcare Professional">
                Healthcare Professional
              </option>

              <option value="Other">
                Other
              </option>

            </select>

          </div>

          <div className="input-group">

            <label>

              <FaHospital />

              Hospital / Organization (Optional)

            </label>

            <input
              type="text"
              name="hospital"
              placeholder="Hospital or Organization"
              value={formData.hospital}
              onChange={handleChange}
            />

          </div>

          <div className="input-group">

            <label>

              <FaStethoscope />

              Specialization (Optional)

            </label>

            <input
              type="text"
              name="specialization"
              placeholder="Example: Oncology, Radiology"
              value={formData.specialization}
              onChange={handleChange}
            />

          </div>

          {error && (

            <div className="profile-error">

              {error}

            </div>

          )}

          <button
            type="submit"
            className="profile-btn"
            disabled={loading}
          >

            {loading ? "Saving..." : "Continue"}

            <FaArrowRight />

          </button>
                  </form>

      </motion.div>

    </div>

  );

}
