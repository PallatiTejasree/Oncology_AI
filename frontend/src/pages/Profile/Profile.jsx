import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useLocation, useNavigate } from "react-router-dom";

import {
  FaArrowLeft,
  FaUser,
  FaEnvelope,
  FaBirthdayCake,
  FaVenusMars,
  FaBriefcase,
  FaCalendarAlt,
  FaEdit,
  FaSave,
} from "react-icons/fa";

import {
  getProfile,
  updateProfile,
} from "../../services/profileService";

import "./Profile.css";

export default function Profile() {

  const navigate = useNavigate();
  const location = useLocation();

  const [loading, setLoading] = useState(true);

  const [saving, setSaving] = useState(false);

  const [editing, setEditing] = useState(false);

  const [profile, setProfile] = useState({

    full_name: "",

    email: "",

    age: "",

    gender: "",

    occupation: "",

    created_at: "",

  });

  useEffect(() => {

    fetchProfile();

  }, []);

  const fetchProfile = async () => {

    try {

      const email = localStorage.getItem("email");

      const data = await getProfile(email);

      setProfile(data);

    }

    catch (err) {

      console.error(err);

    }

    finally {

      setLoading(false);

    }

  };

  const handleChange = (e) => {

    setProfile({

      ...profile,

      [e.target.name]: e.target.value,

    });

  };

  const saveProfile = async () => {

    setSaving(true);

    try {

      await updateProfile(

        profile.email,

        {

          full_name: profile.full_name,

          age: Number(profile.age),

          gender: profile.gender,

          occupation: profile.occupation,

        }

      );

      setEditing(false);

    }

    catch (err) {

      console.error(err);

      alert("Unable to update profile.");

    }

    finally {

      setSaving(false);

    }

  };

  if (loading) {

    return (

      <div className="profile-loading">

        Loading Profile...

      </div>

    );

  }

  return (

    <div className="profile-page">

      <motion.div

        className="profile-card"

        initial={{ opacity: 0, y: 30 }}

        animate={{ opacity: 1, y: 0 }}

        transition={{ duration: 0.5 }}

      >

        <div className="profile-header">

          <button

            className="back-btn"

            onClick={() => {
              const fromSettings = new URLSearchParams(location.search).get("from") === "settings";
              navigate(fromSettings ? "/settings" : "/dashboard");
            }}

          >

            <FaArrowLeft />

          </button>

          <h1>My Profile</h1>

        </div>

        <div className="profile-avatar">

          {profile.full_name
            ? profile.full_name.charAt(0).toUpperCase()
            : "U"}

        </div>
                <div className="profile-info">

          <div className="profile-field">

            <label>
              <FaUser />
              Full Name
            </label>

            {editing ? (

              <input
                type="text"
                name="full_name"
                value={profile.full_name}
                onChange={handleChange}
              />

            ) : (

              <p>{profile.full_name || "-"}</p>

            )}

          </div>

          <div className="profile-field">

            <label>
              <FaEnvelope />
              Email
            </label>

            <p>{profile.email}</p>

          </div>

          <div className="profile-field">

            <label>
              <FaBirthdayCake />
              Age
            </label>

            {editing ? (

              <input
                type="number"
                name="age"
                value={profile.age}
                onChange={handleChange}
              />

            ) : (

              <p>{profile.age || "-"}</p>

            )}

          </div>

          <div className="profile-field">

            <label>
              <FaVenusMars />
              Gender
            </label>

            {editing ? (

              <select
                name="gender"
                value={profile.gender}
                onChange={handleChange}
              >

                <option value="Male">Male</option>

                <option value="Female">Female</option>

                <option value="Other">Other</option>

                <option value="Prefer not to say">
                  Prefer not to say
                </option>

              </select>

            ) : (

              <p>{profile.gender || "-"}</p>

            )}

          </div>

          <div className="profile-field">

            <label>
              <FaBriefcase />
              Occupation
            </label>

            {editing ? (

              <select
                name="occupation"
                value={profile.occupation}
                onChange={handleChange}
              >

                <option value="">Select Occupation</option>

                <option value="Doctor">Doctor</option>

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

                <option value="Student">
                  Student
                </option>

                <option value="Other">
                  Other
                </option>

              </select>

            ) : (

              <p>{profile.occupation || "-"}</p>

            )}

          </div>

          <div className="profile-field">

            <label>
              <FaCalendarAlt />
              Member Since
            </label>

            <p>

              {new Date(
                profile.created_at
              ).toLocaleDateString()}

            </p>

          </div>

        </div>
                <div className="profile-actions">

          {editing ? (

            <>

              <button
                className="save-btn"
                onClick={saveProfile}
                disabled={saving}
              >

                <FaSave />

                {saving
                  ? "Saving..."
                  : "Save Changes"}

              </button>

              <button
                className="cancel-btn"
                onClick={() => {

                  setEditing(false);

                  fetchProfile();

                }}
              >

                Cancel

              </button>

            </>

          ) : (

            <button
              className="edit-btn"
              onClick={() => setEditing(true)}
            >

              <FaEdit />

              Edit Profile

            </button>

          )}

        </div>

      </motion.div>

    </div>

  );

}
